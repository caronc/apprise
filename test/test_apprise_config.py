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

import six
import io
import mock
from apprise import NotifyFormat
from apprise.Apprise import Apprise
from apprise.AppriseConfig import AppriseConfig
from apprise.AppriseAsset import AppriseAsset
from apprise.config.ConfigBase import ConfigBase
from apprise.plugins.NotifyBase import NotifyBase

from apprise.config import SCHEMA_MAP as CONFIG_SCHEMA_MAP
from apprise.plugins import SCHEMA_MAP as NOTIFY_SCHEMA_MAP
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
    """)

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # One configuration file should have been found
    assert len(ac) == 1

    # We should be able to read our 3 servers from that
    assert len(ac.servers()) == 3

    # Get our URL back
    assert isinstance(ac[0].url(), six.string_types)

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

    if six.PY2:
        # decode string into unicode
        istr = istr.decode('utf-8')

    # Write our content to our file
    t = tmpdir.mkdir("internationalization").join("apprise")
    with io.open(str(t), 'wb') as f:
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
    assert isinstance(ac[0].url(), six.string_types)

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

    # Now do the same check but force a flushed cache
    assert len(ac.servers(cache=False)) == 0


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

        def url(self):
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


def test_apprise_instantiate():
    """
    API: AppriseConfig.instantiate()

    """
    assert AppriseConfig.instantiate(
        'file://?', suppress_exceptions=True) is None

    assert AppriseConfig.instantiate(
        'invalid://?', suppress_exceptions=True) is None

    class BadConfig(ConfigBase):
        def __init__(self, **kwargs):
            super(BadConfig, self).__init__(**kwargs)

            # We fail whenever we're initialized
            raise TypeError()

    # Store our bad configuration in our schema map
    CONFIG_SCHEMA_MAP['bad'] = BadConfig

    try:
        AppriseConfig.instantiate(
            'bad://path', suppress_exceptions=False)
        # We should never make it to this line
        assert False

    except TypeError:
        # Exception caught as expected
        assert True

    # Same call but exceptions suppressed
    assert AppriseConfig.instantiate(
        'bad://path', suppress_exceptions=True) is None


def test_apprise_config_with_apprise_obj(tmpdir):
    """
    API: ConfigBase.parse_inaccessible_text_file

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

        def url(self):
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

    # Generate ourselfs a fake entry
    apprise.config.ConfigDummy = ConfigDummy
    apprise.config.ConfigDummy2 = ConfigDummy2
    apprise.config.ConfigDummy3 = ConfigDummy3
    apprise.config.ConfigDummy4 = ConfigDummy4

    __load_matrix()

    # Call it again so we detect our entries already loaded
    __load_matrix()


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


def test_config_base_parse_yaml_file(tmpdir):
    """
    API: ConfigBase.parse_yaml_file

    """
    t = tmpdir.mkdir("empty-file").join("apprise.yml")
    t.write("")

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # The number of configuration files that exist
    assert len(ac) == 1

    # no notifications are loaded
    assert len(ac.servers()) == 0
