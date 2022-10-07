# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys
import pytest
from unittest import mock
from apprise import NotifyFormat
from apprise import ConfigFormat
from apprise import ContentIncludeMode
from apprise import Apprise
from apprise import AppriseConfig
from apprise import AppriseAsset
from apprise.config.ConfigBase import ConfigBase
from apprise.plugins.NotifyBase import NotifyBase

from apprise.common import CONFIG_SCHEMA_MAP
from apprise.common import NOTIFY_SCHEMA_MAP
from apprise.config import __load_matrix
from apprise.config.ConfigFile import ConfigFile

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_apprise_config(tmpdir):
    """
    API: AppriseConfig basic testing

    """

    # Create ourselves a config object
    ac = AppriseConfig()

    # There are no servers loaded
    assert len(ac) == 0

    # Object can be directly checked as a boolean; response is False
    # when there are no entries loaded
    assert not ac

    # lets try anyway
    assert len(ac.servers()) == 0

    t = tmpdir.mkdir("simple-formatting").join("apprise")
    t.write("""
    # A comment line over top of a URL
    mailto://usera:pass@gmail.com

    # A line with mulitiple tag assignments to it
    taga,tagb=gnome://

    # Event if there is accidental leading spaces, this configuation
    # is accepting of htat and will not exclude them
                tagc=kde://

    # A very poorly structured url
    sns://:@/

    # Just 1 token provided causes exception
    sns://T1JJ3T3L2/

    # XML
    xml://localhost/?+HeaderEntry=Test&:IgnoredEntry=Ignored
    """)

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # One configuration file should have been found
    assert len(ac) == 1

    # Object can be directly checked as a boolean; response is True
    # when there is at least one entry
    assert ac

    # We should be able to read our 4 servers from that
    assert len(ac.servers()) == 4

    # Get our URL back
    assert isinstance(ac[0].url(), str)

    # Test cases where our URL is invalid
    t = tmpdir.mkdir("strange-lines").join("apprise")
    t.write("""
    # basicly this consists of defined tags and no url
    tag=
    """)

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t), asset=AppriseAsset())

    # One configuration file should have been found
    assert len(ac) == 1

    # No urls were set
    assert len(ac.servers()) == 0

    # Create a ConfigBase object
    cb = ConfigBase()

    # Test adding of all entries
    assert ac.add(configs=cb, asset=AppriseAsset(), tag='test') is True

    # Test adding of all entries
    assert ac.add(
        configs=['file://?', ], asset=AppriseAsset(), tag='test') is False

    # Test the adding of garbage
    assert ac.add(configs=object()) is False

    # Try again but enforce our format
    ac = AppriseConfig(paths='file://{}?format=text'.format(str(t)))

    # One configuration file should have been found
    assert len(ac) == 1

    # No urls were set
    assert len(ac.servers()) == 0

    #
    # Test Internatialization and the handling of unicode characters
    #
    istr = """
        # Iñtërnâtiônàlization Testing
        windows://"""

    # Write our content to our file
    t = tmpdir.mkdir("internationalization").join("apprise")
    with open(str(t), 'wb') as f:
        f.write(istr.encode('latin-1'))

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # One configuration file should have been found
    assert len(ac) == 1

    # This will fail because our default encoding is utf-8; however the file
    # we opened was not; it was latin-1 and could not be parsed.
    assert len(ac.servers()) == 0

    # Test iterator
    count = 0
    for entry in ac:
        count += 1
    assert len(ac) == count

    # We can fix this though; set our encoding to latin-1
    ac = AppriseConfig(paths='file://{}?encoding=latin-1'.format(str(t)))

    # One configuration file should have been found
    assert len(ac) == 1

    # Our URL should be found
    assert len(ac.servers()) == 1

    # Get our URL back
    assert isinstance(ac[0].url(), str)

    # pop an entry from our list
    assert isinstance(ac.pop(0), ConfigBase) is True

    # Determine we have no more configuration entries loaded
    assert len(ac) == 0

    #
    # Test buffer handling (and overflow)
    t = tmpdir.mkdir("buffer-handling").join("apprise")
    buf = "gnome://"
    t.write(buf)

    # Reset our config object
    ac.clear()

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # update our length to be the size of our actual file
    ac[0].max_buffer_size = len(buf)

    # One configuration file should have been found
    assert len(ac) == 1

    assert len(ac.servers()) == 1

    # update our buffer size to be slightly smaller then what we allow
    ac[0].max_buffer_size = len(buf) - 1

    # Content is automatically cached; so even though we adjusted the buffer
    # above, our results have been cached so we get a 1 response.
    assert len(ac.servers()) == 1


def test_apprise_multi_config_entries(tmpdir):
    """
    API: AppriseConfig basic multi-adding functionality

    """
    # temporary file to work with
    t = tmpdir.mkdir("apprise-multi-add").join("apprise")
    buf = """
    good://hostname
    """
    t.write(buf)

    # temporary empty file to work with
    te = tmpdir.join("apprise-multi-add", "apprise-empty")
    te.write("")

    # Define our good:// url
    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(GoodNotification, self).__init__(
                notify_format=NotifyFormat.HTML, **kwargs)

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # support url()
            return ''

    # Store our good notification in our schema map
    NOTIFY_SCHEMA_MAP['good'] = GoodNotification

    # Create ourselves a config object
    ac = AppriseConfig()

    # There are no servers loaded
    assert len(ac) == 0

    # Support adding of muilt strings and objects:
    assert ac.add(configs=(str(t), str(t))) is True
    assert ac.add(configs=(
        ConfigFile(path=str(te)), ConfigFile(path=str(t)))) is True

    # don't support the adding of invalid content
    assert ac.add(configs=(object(), object())) is False
    assert ac.add(configs=object()) is False

    # Try to pop an element out of range
    try:
        ac.server_pop(len(ac.servers()))
        # We should have thrown an exception here
        assert False

    except IndexError:
        # We expect to be here
        assert True

    # Pop our elements
    while len(ac.servers()) > 0:
        assert isinstance(
            ac.server_pop(len(ac.servers()) - 1), NotifyBase) is True


def test_apprise_add_config():
    """
    API AppriseConfig.add_config()

    """
    content = """
    # A comment line over top of a URL
    mailto://usera:pass@gmail.com

    # A line with mulitiple tag assignments to it
    taga,tagb=gnome://

    # Event if there is accidental leading spaces, this configuation
    # is accepting of htat and will not exclude them
                tagc=kde://

    # A very poorly structured url
    sns://:@/

    # Just 1 token provided causes exception
    sns://T1JJ3T3L2/
    """
    # Create ourselves a config object
    ac = AppriseConfig()
    assert ac.add_config(content=content) is True

    # One configuration file should have been found
    assert len(ac) == 1
    assert ac[0].config_format is ConfigFormat.TEXT

    # Object can be directly checked as a boolean; response is True
    # when there is at least one entry
    assert ac

    # We should be able to read our 3 servers from that
    assert len(ac.servers()) == 3

    # Get our URL back
    assert isinstance(ac[0].url(), str)

    # Test invalid content
    assert ac.add_config(content=object()) is False
    assert ac.add_config(content=42) is False
    assert ac.add_config(content=None) is False

    # Still only one server loaded
    assert len(ac) == 1

    # Test having a pre-defined asset object and tag created
    assert ac.add_config(
        content=content, asset=AppriseAsset(), tag='a') is True

    # Now there are 2 servers loaded
    assert len(ac) == 2

    # and 6 urls.. (as we've doubled up)
    assert len(ac.servers()) == 6

    content = """
    # A YAML File
    urls:
       - mailto://usera:pass@gmail.com
       - gnome://:
          tag: taga,tagb

       - json://localhost:
          +HeaderEntry1: 'a header entry'
          -HeaderEntryDepricated: 'a deprecated entry'
          :HeaderEntryIgnored: 'an ignored header entry'

       - xml://localhost:
          +HeaderEntry1: 'a header entry'
          -HeaderEntryDepricated: 'a deprecated entry'
          :HeaderEntryIgnored: 'an ignored header entry'
    """

    # Create ourselves a config object
    ac = AppriseConfig()
    assert ac.add_config(content=content) is True

    # One configuration file should have been found
    assert len(ac) == 1
    assert ac[0].config_format is ConfigFormat.YAML

    # Object can be directly checked as a boolean; response is True
    # when there is at least one entry
    assert ac

    # We should be able to read our 4 servers from that
    assert len(ac.servers()) == 4

    # Now an invalid configuration file
    content = "invalid"

    # Create ourselves a config object
    ac = AppriseConfig()
    assert ac.add_config(content=content) is False

    # Nothing is loaded
    assert len(ac.servers()) == 0


def test_apprise_config_tagging(tmpdir):
    """
    API: AppriseConfig tagging

    """

    # temporary file to work with
    t = tmpdir.mkdir("tagging").join("apprise")
    buf = "gnome://"
    t.write(buf)

    # Create ourselves a config object
    ac = AppriseConfig()

    # Add an item associated with tag a
    assert ac.add(configs=str(t), asset=AppriseAsset(), tag='a') is True
    # Add an item associated with tag b
    assert ac.add(configs=str(t), asset=AppriseAsset(), tag='b') is True
    # Add an item associated with tag a or b
    assert ac.add(configs=str(t), asset=AppriseAsset(), tag='a,b') is True

    # Now filter: a:
    assert len(ac.servers(tag='a')) == 2
    # Now filter: a or b:
    assert len(ac.servers(tag='a,b')) == 3
    # Now filter: a and b
    assert len(ac.servers(tag=[('a', 'b')])) == 1
    # all matches everything
    assert len(ac.servers(tag='all')) == 3

    # Test cases using the `always` keyword
    # Create ourselves a config object
    ac = AppriseConfig()

    # Add an item associated with tag a
    assert ac.add(configs=str(t), asset=AppriseAsset(), tag='a,always') is True
    # Add an item associated with tag b
    assert ac.add(configs=str(t), asset=AppriseAsset(), tag='b') is True
    # Add an item associated with tag a or b
    assert ac.add(configs=str(t), asset=AppriseAsset(), tag='c,d') is True

    # Now filter: a:
    assert len(ac.servers(tag='a')) == 1
    # Now filter: a or b:
    assert len(ac.servers(tag='a,b')) == 2
    # Now filter: e
    # we'll match the `always'
    assert len(ac.servers(tag='e')) == 1
    assert len(ac.servers(tag='e', match_always=False)) == 0
    # all matches everything
    assert len(ac.servers(tag='all')) == 3

    # Now filter: d
    # we'll match the `always' tag
    assert len(ac.servers(tag='d')) == 2
    assert len(ac.servers(tag='d', match_always=False)) == 1


def test_apprise_config_instantiate():
    """
    API: AppriseConfig.instantiate()

    """
    assert AppriseConfig.instantiate(
        'file://?', suppress_exceptions=True) is None

    assert AppriseConfig.instantiate(
        'invalid://?', suppress_exceptions=True) is None

    class BadConfig(ConfigBase):
        # always allow incusion
        allow_cross_includes = ContentIncludeMode.ALWAYS

        def __init__(self, **kwargs):
            super(BadConfig, self).__init__(**kwargs)

            # We fail whenever we're initialized
            raise TypeError()

        @staticmethod
        def parse_url(url, *args, **kwargs):
            # always parseable
            return ConfigBase.parse_url(url, verify_host=False)

    # Store our bad configuration in our schema map
    CONFIG_SCHEMA_MAP['bad'] = BadConfig

    with pytest.raises(TypeError):
        AppriseConfig.instantiate(
            'bad://path', suppress_exceptions=False)

    # Same call but exceptions suppressed
    assert AppriseConfig.instantiate(
        'bad://path', suppress_exceptions=True) is None


def test_invalid_apprise_config(tmpdir):
    """
    Parse invalid configuration includes

    """

    class BadConfig(ConfigBase):
        # always allow incusion
        allow_cross_includes = ContentIncludeMode.ALWAYS

        def __init__(self, **kwargs):
            super(BadConfig, self).__init__(**kwargs)

            # We intentionally fail whenever we're initialized
            raise TypeError()

        @staticmethod
        def parse_url(url, *args, **kwargs):
            # always parseable
            return ConfigBase.parse_url(url, verify_host=False)

    # Store our bad configuration in our schema map
    CONFIG_SCHEMA_MAP['bad'] = BadConfig

    # temporary file to work with
    t = tmpdir.mkdir("apprise-bad-obj").join("invalid")
    buf = """
    # Include an invalid schema
    include invalid://

    # An unparsable valid schema
    include https://

    # A valid configuration that will throw an exception
    include bad://

    # Include ourselves (So our recursive includes fails as well)
    include {}

    """.format(str(t))
    t.write(buf)

    # Create ourselves a config object with caching disbled
    ac = AppriseConfig(recursion=2, insecure_includes=True, cache=False)

    # Nothing loaded yet
    assert len(ac) == 0

    # Add our config
    assert ac.add(configs=str(t), asset=AppriseAsset()) is True

    # One configuration file
    assert len(ac) == 1

    # All of the servers were invalid and would not load
    assert len(ac.servers()) == 0


def test_apprise_config_with_apprise_obj(tmpdir):
    """
    API: ConfigBase - parse valid config

    """

    # temporary file to work with
    t = tmpdir.mkdir("apprise-obj").join("apprise")
    buf = """
    good://hostname
    localhost=good://localhost
    """
    t.write(buf)

    # Define our good:// url
    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(GoodNotification, self).__init__(
                notify_format=NotifyFormat.HTML, **kwargs)

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # support url()
            return ''

    # Store our good notification in our schema map
    NOTIFY_SCHEMA_MAP['good'] = GoodNotification

    # Create ourselves a config object
    ac = AppriseConfig(cache=False)

    # Nothing loaded yet
    assert len(ac) == 0

    # Add an item associated with tag a
    assert ac.add(configs=str(t), asset=AppriseAsset(), tag='a') is True

    # One configuration file
    assert len(ac) == 1

    # 2 services found in it
    assert len(ac.servers()) == 2

    # Pop one of them (at index 0)
    ac.server_pop(0)

    # Verify that it no longer listed
    assert len(ac.servers()) == 1

    # Test our ability to add Config objects to our apprise object
    a = Apprise()

    # Add our configuration object
    assert a.add(servers=ac) is True

    # Detect our 1 entry (originally there were 2 but we deleted one)
    assert len(a) == 1

    # Notify our service
    assert a.notify(body='apprise configuration power!') is True

    # Add our configuration object
    assert a.add(
        servers=[AppriseConfig(str(t)), AppriseConfig(str(t))]) is True

    # Detect our 5 loaded entries now; 1 from first config, and another
    # 2x2 based on adding our list above
    assert len(a) == 5

    # We can't add garbage
    assert a.add(servers=object()) is False
    assert a.add(servers=[object(), object()]) is False

    # Our length is unchanged
    assert len(a) == 5

    # reference index 0 of our list
    ref = a[0]
    assert isinstance(ref, NotifyBase) is True

    # Our length is unchanged
    assert len(a) == 5

    # pop the index
    ref_popped = a.pop(0)

    # Verify our response
    assert isinstance(ref_popped, NotifyBase) is True

    # Our length drops by 1
    assert len(a) == 4

    # Content popped is the same as one referenced by index
    # earlier
    assert ref == ref_popped

    # pop an index out of range
    try:
        a.pop(len(a))
        # We'll thrown an IndexError and not make it this far
        assert False

    except IndexError:
        # As expected
        assert True

    # Our length remains unchanged
    assert len(a) == 4

    # Reference content out of range
    try:
        a[len(a)]

        # We'll thrown an IndexError and not make it this far
        assert False

    except IndexError:
        # As expected
        assert True

    # reference index at the end of our list
    ref = a[len(a) - 1]

    # Verify our response
    assert isinstance(ref, NotifyBase) is True

    # Our length stays the same
    assert len(a) == 4

    # We can pop from the back of the list without a problem too
    ref_popped = a.pop(len(a) - 1)

    # Verify our response
    assert isinstance(ref_popped, NotifyBase) is True

    # Content popped is the same as one referenced by index
    # earlier
    assert ref == ref_popped

    # Our length drops by 1
    assert len(a) == 3

    # Now we'll test adding another element to the list so that it mixes up
    # our response object.
    # Below we add 3 different types, a ConfigBase, NotifyBase, and URL
    assert a.add(
        servers=[
            ConfigFile(path=(str(t))),
            'good://another.host',
            GoodNotification(**{'host': 'nuxref.com'})]) is True

    # Our length increases by 4 (2 entries in the config file, + 2 others)
    assert len(a) == 7

    # reference index at the end of our list
    ref = a[len(a) - 1]

    # Verify our response
    assert isinstance(ref, NotifyBase) is True

    # We can pop from the back of the list without a problem too
    ref_popped = a.pop(len(a) - 1)

    # Verify our response
    assert isinstance(ref_popped, NotifyBase) is True

    # Content popped is the same as one referenced by index
    # earlier
    assert ref == ref_popped

    # Our length drops by 1
    assert len(a) == 6

    # pop our list
    while len(a) > 0:
        assert isinstance(a.pop(len(a) - 1), NotifyBase) is True


def test_recursive_config_inclusion(tmpdir):
    """
    API: Apprise() Recursive Config Inclusion

    """

    # To test our config classes, we make three dummy configs
    class ConfigCrossPostAlways(ConfigFile):
        """
        A dummy config that is set to always allow inclusion
        """

        service_name = 'always'

        # protocol
        protocol = 'always'

        # Always type
        allow_cross_includes = ContentIncludeMode.ALWAYS

    class ConfigCrossPostStrict(ConfigFile):
        """
        A dummy config that is set to strict inclusion
        """

        service_name = 'strict'

        # protocol
        protocol = 'strict'

        # Always type
        allow_cross_includes = ContentIncludeMode.STRICT

    class ConfigCrossPostNever(ConfigFile):
        """
        A dummy config that is set to never allow inclusion
        """

        service_name = 'never'

        # protocol
        protocol = 'never'

        # Always type
        allow_cross_includes = ContentIncludeMode.NEVER

    # store our entries
    CONFIG_SCHEMA_MAP['never'] = ConfigCrossPostNever
    CONFIG_SCHEMA_MAP['strict'] = ConfigCrossPostStrict
    CONFIG_SCHEMA_MAP['always'] = ConfigCrossPostAlways

    # Make our new path valid
    suite = tmpdir.mkdir("apprise_config_recursion")

    cfg01 = suite.join("cfg01.cfg")
    cfg02 = suite.mkdir("dir1").join("cfg02.cfg")
    cfg03 = suite.mkdir("dir2").join("cfg03.cfg")
    cfg04 = suite.mkdir("dir3").join("cfg04.cfg")

    # Populate our files with valid configuration include lines
    cfg01.write("""
# json entry
json://localhost:8080

# absolute path inclusion to ourselves
include {}""".format(str(cfg01)))

    cfg02.write("""
# syslog entry
syslog://

# recursively include ourselves
include cfg02.cfg""")

    cfg03.write("""
# xml entry
xml://localhost:8080

# relative path inclusion
include ../dir1/cfg02.cfg

# test that we can't include invalid entries
include invalid://entry

# Include non includable type
include memory://""")

    cfg04.write("""
# xml entry
xml://localhost:8080

# always include of our file
include always://{}

# never include of our file
include never://{}

# strict include of our file
include strict://{}""".format(str(cfg04), str(cfg04), str(cfg04)))

    # Create ourselves a config object
    ac = AppriseConfig()

    # There are no servers loaded
    assert len(ac) == 0

    # load our configuration
    assert ac.add(configs=str(cfg01)) is True

    # verify it loaded
    assert len(ac) == 1

    # 1 service will be loaded as there is no recursion at this point
    assert len(ac.servers()) == 1

    # Create ourselves a config object
    ac = AppriseConfig(recursion=1)

    # load our configuration
    assert ac.add(configs=str(cfg01)) is True

    # verify one configuration file loaded however since it recursively
    # loaded itself 1 more time, it still doesn't impact the load count:
    assert len(ac) == 1

    # 2 services loaded now that we loaded the same file twice
    assert len(ac.servers()) == 2

    #
    # Now we test relative file inclusion
    #

    # Create ourselves a config object
    ac = AppriseConfig(recursion=10)

    # There are no servers loaded
    assert len(ac) == 0

    # load our configuration
    assert ac.add(configs=str(cfg02)) is True

    # verify it loaded
    assert len(ac) == 1

    # 11 services loaded because we reloaded ourselves 10 times
    # after loading the first entry
    assert len(ac.servers()) == 11

    # Test our include modes (strict, always, and never)

    # Create ourselves a config object
    ac = AppriseConfig(recursion=1)

    # There are no servers loaded
    assert len(ac) == 0

    # load our configuration
    assert ac.add(configs=str(cfg04)) is True

    # verify it loaded
    assert len(ac) == 1

    # 2 servers loaded
    # 1 - from the file read (which is set at mode STRICT
    # 1 - from the always://
    #
    # The never:// can ever be includeed, and the strict:// is ot of type
    #  file:// (the one doing the include) so it is also ignored.
    #
    # By turning on the insecure_includes, we can include the strict files too
    assert len(ac.servers()) == 2

    # Create ourselves a config object
    ac = AppriseConfig(recursion=1, insecure_includes=True)

    # There are no servers loaded
    assert len(ac) == 0

    # load our configuration
    assert ac.add(configs=str(cfg04)) is True

    # verify it loaded
    assert len(ac) == 1

    # 3 servers loaded
    # 1 - from the file read (which is set at mode STRICT
    # 1 - from the always://
    # 1 - from the strict:// (due to insecure_includes set)
    assert len(ac.servers()) == 3


def test_apprise_config_matrix_load():
    """
    API: AppriseConfig() matrix initialization

    """

    import apprise

    class ConfigDummy(ConfigBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy'

        # protocol as tuple
        protocol = ('uh', 'oh')

        # secure protocol as tuple
        secure_protocol = ('no', 'yes')

    class ConfigDummy2(ConfigBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy2'

        # secure protocol as tuple
        secure_protocol = ('true', 'false')

    class ConfigDummy3(ConfigBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy3'

        # secure protocol as string
        secure_protocol = 'true'

    class ConfigDummy4(ConfigBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy4'

        # protocol as string
        protocol = 'true'

    # Generate ourselves a fake entry
    apprise.config.ConfigDummy = ConfigDummy
    apprise.config.ConfigDummy2 = ConfigDummy2
    apprise.config.ConfigDummy3 = ConfigDummy3
    apprise.config.ConfigDummy4 = ConfigDummy4

    __load_matrix()

    # Call it again so we detect our entries already loaded
    __load_matrix()


def test_configmatrix_dynamic_importing(tmpdir):
    """
    API: Apprise() Config Matrix Importing

    """

    # Make our new path valid
    suite = tmpdir.mkdir("apprise_config_test_suite")
    suite.join("__init__.py").write('')

    module_name = 'badconfig'

    # Update our path to point to our new test suite
    sys.path.insert(0, str(suite))

    # Create a base area to work within
    base = suite.mkdir(module_name)
    base.join("__init__.py").write('')

    # Test no app_id
    base.join('ConfigBadFile1.py').write(
        """
class ConfigBadFile1:
    pass""")

    # No class of the same name
    base.join('ConfigBadFile2.py').write(
        """
class BadClassName:
    pass""")

    # Exception thrown
    base.join('ConfigBadFile3.py').write("""raise ImportError()""")

    # Utilizes a schema:// already occupied (as string)
    base.join('ConfigGoober.py').write(
        """
from apprise.config import ConfigBase
class ConfigGoober(ConfigBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol (used by ConfigHTTP)
    protocol = ('http', 'goober')

    # The default secure protocol (used by ConfigHTTP)
    secure_protocol = 'https'

    @staticmethod
    def parse_url(url, *args, **kwargs):
        # always parseable
        return ConfigBase.parse_url(url, verify_host=False)""")

    # Utilizes a schema:// already occupied (as tuple)
    base.join('ConfigBugger.py').write("""
from apprise.config import ConfigBase
class ConfigBugger(ConfigBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol (used by ConfigHTTP), the other
    # isn't
    protocol = ('http', 'bugger-test' )

    # The default secure protocol (used by ConfigHTTP), the other isn't
    secure_protocol = ('https', ['garbage'])

    @staticmethod
    def parse_url(url, *args, **kwargs):
        # always parseable
        return ConfigBase.parse_url(url, verify_host=False)""")

    __load_matrix(path=str(base), name=module_name)


@mock.patch('os.path.getsize')
def test_config_base_parse_inaccessible_text_file(mock_getsize, tmpdir):
    """
    API: ConfigBase.parse_inaccessible_text_file

    """

    # temporary file to work with
    t = tmpdir.mkdir("inaccessible").join("apprise")
    buf = "gnome://"
    t.write(buf)

    # Set getsize return value
    mock_getsize.return_value = None
    mock_getsize.side_effect = OSError

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # The following internally throws an exception but still counts
    # as a loaded configuration file
    assert len(ac) == 1

    # Thus no notifications are loaded
    assert len(ac.servers()) == 0


def test_config_base_parse_yaml_file01(tmpdir):
    """
    API: ConfigBase.parse_yaml_file (#1)

    """
    t = tmpdir.mkdir("empty-file").join("apprise.yml")
    t.write("")

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # The number of configuration files that exist
    assert len(ac) == 1

    # no notifications are loaded
    assert len(ac.servers()) == 0


def test_config_base_parse_yaml_file02(tmpdir):
    """
    API: ConfigBase.parse_yaml_file (#2)

    """
    t = tmpdir.mkdir("matching-tags").join("apprise.yml")
    t.write("""urls:
  - pover://nsisxnvnqixq39t0cw54pxieyvtdd9@2jevtmstfg5a7hfxndiybasttxxfku:
    - tag: test1
  - pover://rg8ta87qngcrkc6t4qbykxktou0uug@tqs3i88xlufexwl8t4asglt4zp5wfn:
    - tag: test2
  - pover://jcqgnlyq2oetea4qg3iunahj8d5ijm@evalvutkhc8ipmz2lcgc70wtsm0qpb:
    - tag: test3""")

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # The number of configuration files that exist
    assert len(ac) == 1

    # no notifications are loaded
    assert len(ac.servers()) == 3

    # Test our ability to add Config objects to our apprise object
    a = Apprise()

    # Add our configuration object
    assert a.add(servers=ac) is True

    # Detect our 3 entry as they should have loaded successfully
    assert len(a) == 3

    # No match
    assert sum(1 for _ in a.find('no-match')) == 0
    # Match everything
    assert sum(1 for _ in a.find('all')) == 3
    # Match test1 entry
    assert sum(1 for _ in a.find('test1')) == 1
    # Match test2 entry
    assert sum(1 for _ in a.find('test2')) == 1
    # Match test3 entry
    assert sum(1 for _ in a.find('test3')) == 1
    # Match test1 or test3 entry
    assert sum(1 for _ in a.find('test1, test3')) == 2


def test_config_base_parse_yaml_file03(tmpdir):
    """
    API: ConfigBase.parse_yaml_file (#3)

    """

    t = tmpdir.mkdir("bad-first-entry").join("apprise.yml")
    # The first entry is -tag and not <dash><space>tag
    # The element is therefore not picked up; This causes us to display
    # some warning messages to the screen complaining of this typo yet
    # still allowing us to load the URL since it is valid
    t.write("""urls:
  - pover://nsisxnvnqixq39t0cw54pxieyvtdd9@2jevtmstfg5a7hfxndiybasttxxfku:
    -tag: test1
  - pover://rg8ta87qngcrkc6t4qbykxktou0uug@tqs3i88xlufexwl8t4asglt4zp5wfn:
    - tag: test2
  - pover://jcqgnlyq2oetea4qg3iunahj8d5ijm@evalvutkhc8ipmz2lcgc70wtsm0qpb:
    - tag: test3""")

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # The number of configuration files that exist
    assert len(ac) == 1

    # no notifications lines processed is 3
    assert len(ac.servers()) == 3

    # Test our ability to add Config objects to our apprise object
    a = Apprise()

    # Add our configuration object
    assert a.add(servers=ac) is True

    # Detect our 3 entry as they should have loaded successfully
    assert len(a) == 3

    # No match
    assert sum(1 for _ in a.find('no-match')) == 0
    # Match everything
    assert sum(1 for _ in a.find('all')) == 3
    # No match for bad entry
    assert sum(1 for _ in a.find('test1')) == 0
    # Match test2 entry
    assert sum(1 for _ in a.find('test2')) == 1
    # Match test3 entry
    assert sum(1 for _ in a.find('test3')) == 1
    # Match test1 or test3 entry; (only matches test3)
    assert sum(1 for _ in a.find('test1, test3')) == 1


def test_config_base_parse_yaml_file04(tmpdir):
    """
    API: ConfigBase.parse_yaml_file (#4)

    Test the always keyword

    """
    t = tmpdir.mkdir("always-keyword").join("apprise.yml")
    t.write("""urls:
  - pover://nsisxnvnqixq39t0cw54pxieyvtdd9@2jevtmstfg5a7hfxndiybasttxxfku:
    - tag: test1,always
  - pover://rg8ta87qngcrkc6t4qbykxktou0uug@tqs3i88xlufexwl8t4asglt4zp5wfn:
    - tag: test2
  - pover://jcqgnlyq2oetea4qg3iunahj8d5ijm@evalvutkhc8ipmz2lcgc70wtsm0qpb:
    - tag: test3""")

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # The number of configuration files that exist
    assert len(ac) == 1

    # no notifications are loaded
    assert len(ac.servers()) == 3

    # Test our ability to add Config objects to our apprise object
    a = Apprise()

    # Add our configuration object
    assert a.add(servers=ac) is True

    # Detect our 3 entry as they should have loaded successfully
    assert len(a) == 3

    # No match still matches `always` keyword
    assert sum(1 for _ in a.find('no-match')) == 1
    # Unless we explicitly do not look for that file
    assert sum(1 for _ in a.find('no-match', match_always=False)) == 0
    # Match everything
    assert sum(1 for _ in a.find('all')) == 3
    # Match test1 entry (also has `always` keyword
    assert sum(1 for _ in a.find('test1')) == 1
    assert sum(1 for _ in a.find('test1', match_always=False)) == 1
    # Match test2 entry (and test1 due to always keyword)
    assert sum(1 for _ in a.find('test2')) == 2
    assert sum(1 for _ in a.find('test2', match_always=False)) == 1
    # Match test3 entry (and test1 due to always keyword)
    assert sum(1 for _ in a.find('test3')) == 2
    assert sum(1 for _ in a.find('test3', match_always=False)) == 1
    # Match test1 or test3 entry
    assert sum(1 for _ in a.find('test1, test3')) == 2


def test_apprise_config_template_parse(tmpdir):
    """
    API: AppriseConfig parsing of templates

    """

    # Create ourselves a config object
    ac = AppriseConfig()

    t = tmpdir.mkdir("template-testing").join("apprise.yml")
    t.write("""

    tag:
      - company

    # A comment line over top of a URL
    urls:
       - mailto://user:pass@example.com:
          - to: user1@gmail.com
            cc: test@hotmail.com

          - to: user2@gmail.com
            tag: co-worker
    """)

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # 2 emails to be sent
    assert len(ac.servers()) == 2

    # The below checks are very customized for NotifyMail but just
    # test that the content got passed correctly
    assert (False, 'user1@gmail.com') in ac[0][0].targets
    assert 'test@hotmail.com' in ac[0][0].cc
    assert 'company' in ac[0][1].tags

    assert (False, 'user2@gmail.com') in ac[0][1].targets
    assert 'company' in ac[0][1].tags
    assert 'co-worker' in ac[0][1].tags

    #
    # Specifically test _special_token_handler()
    #
    tokens = {
        # This maps to itself (bcc); no change here
        'bcc': 'user@test.com',
        # This should get mapped to 'targets'
        'to': 'user1@abc.com',
        # white space and tab is intentionally added to the end to verify we
        # do not play/tamper with information
        'targets': 'user2@abc.com, user3@abc.com   \t',
        # If the end user provides a configuration for data we simply don't use
        # this isn't a proble... we simply don't touch it either; we leave it
        # as is.
        'ignore': 'not-used'
    }

    result = ConfigBase._special_token_handler('mailto', tokens)
    # to gets mapped to targets
    assert 'to' not in result

    # bcc is allowed here
    assert 'bcc' in result
    assert 'targets' in result
    # Not used, but also not touched; this entry should still be in our result
    # set
    assert 'ignore' in result
    # We'll concatinate all of our targets together
    assert len(result['targets']) == 2
    assert 'user1@abc.com' in result['targets']
    # Content is passed as is
    assert 'user2@abc.com, user3@abc.com   \t' in result['targets']

    # We re-do the simmiar test above.  The very key difference is the
    # `targets` is a list already (it's expected type) so `to` can properly be
    # concatinated into the list vs the above (which tries to correct the
    # situation)
    tokens = {
        # This maps to itself (bcc); no change here
        'bcc': 'user@test.com',
        # This should get mapped to 'targets'
        'to': 'user1@abc.com',
        # similar to the above test except targets is now a proper
        # dictionary allowing the `to` (when translated to `targets`) to get
        # appended to it
        'targets': ['user2@abc.com', 'user3@abc.com'],
        # If the end user provides a configuration for data we simply don't use
        # this isn't a proble... we simply don't touch it either; we leave it
        # as is.
        'ignore': 'not-used'
    }

    result = ConfigBase._special_token_handler('mailto', tokens)
    # to gets mapped to targets
    assert 'to' not in result

    # bcc is allowed here
    assert 'bcc' in result
    assert 'targets' in result
    # Not used, but also not touched; this entry should still be in our result
    # set
    assert 'ignore' in result

    # Now we'll see the new user added as expected (concatinated into our list)
    assert len(result['targets']) == 3
    assert 'user1@abc.com' in result['targets']
    assert 'user2@abc.com' in result['targets']
    assert 'user3@abc.com' in result['targets']

    # Test providing a list
    t.write("""
    # A comment line over top of a URL
    urls:
       - mailtos://user:pass@example.com:
          - smtp: smtp3-dev.google.gmail.com
            to:
              - John Smith <user1@gmail.com>
              - Jason Tater <user2@gmail.com>
              - user3@gmail.com

          - to: Henry Fisher <user4@gmail.com>, Jason Archie <user5@gmail.com>
            smtp_host: smtp5-dev.google.gmail.com
            tag: drinking-buddy

       # provide case where the URL includes some input too
       # In both of these cases, the cc and targets (to) get over-ridden
       # by values below
       - mailtos://user:pass@example.com/arnold@imdb.com/?cc=bill@micro.com/:
            to:
              - override01@gmail.com
            cc:
              - override02@gmail.com

       - sinch://:
          - spi: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
            token: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb

            # Test a case where we expect a string, but yaml reads it in as
            # a number
            from: 10005243890
            to: +1(123)555-1234
    """)

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # 2 emails to be sent and 1 Sinch service call
    assert len(ac.servers()) == 4

    # Verify our users got placed into the to
    assert len(ac[0][0].targets) == 3
    assert ("John Smith", 'user1@gmail.com') in ac[0][0].targets
    assert ("Jason Tater", 'user2@gmail.com') in ac[0][0].targets
    assert (False, 'user3@gmail.com') in ac[0][0].targets
    assert ac[0][0].smtp_host == 'smtp3-dev.google.gmail.com'

    assert len(ac[0][1].targets) == 2
    assert ("Henry Fisher", 'user4@gmail.com') in ac[0][1].targets
    assert ("Jason Archie", 'user5@gmail.com') in ac[0][1].targets
    assert 'drinking-buddy' in ac[0][1].tags
    assert ac[0][1].smtp_host == 'smtp5-dev.google.gmail.com'

    # Our third test tests cases where some variables are defined inline
    # and additional ones are defined below that share the same token space
    assert len(ac[0][2].targets) == 1
    assert len(ac[0][2].cc) == 1
    assert (False, 'override01@gmail.com') in ac[0][2].targets
    assert 'override02@gmail.com' in ac[0][2].cc

    # Test our Since configuration now:
    assert len(ac[0][3].targets) == 1
    assert ac[0][3].service_plan_id == 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    assert ac[0][3].source == '+10005243890'
    assert ac[0][3].targets[0] == '+11235551234'
