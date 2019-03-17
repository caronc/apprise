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
import six
from apprise.AppriseAsset import AppriseAsset
from apprise.config.ConfigBase import ConfigBase
from apprise.config import __load_matrix

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_config_base():
    """
    API: ConfigBase() object

    """

    # invalid types throw exceptions
    try:
        ConfigBase(**{'format': 'invalid'})
        # We should never reach here as an exception should be thrown
        assert(False)

    except TypeError:
        assert(True)

    # Config format types are not the same as ConfigBase ones
    try:
        ConfigBase(**{'format': 'markdown'})
        # We should never reach here as an exception should be thrown
        assert(False)

    except TypeError:
        assert(True)

    cb = ConfigBase(**{'format': 'yaml'})
    assert isinstance(cb, ConfigBase)

    cb = ConfigBase(**{'format': 'text'})
    assert isinstance(cb, ConfigBase)

    # Set encoding
    cb = ConfigBase(encoding='utf-8', format='text')
    assert isinstance(cb, ConfigBase)

    # read is not supported in the base object; only the children
    assert cb.read() is None

    # There are no servers loaded on a freshly created object
    assert len(cb.servers()) == 0

    # Unsupported URLs are not parsed
    assert ConfigBase.parse_url(url='invalid://') is None

    # Valid URL & Valid Format
    results = ConfigBase.parse_url(
        url='file://relative/path?format=yaml&encoding=latin-1')
    assert isinstance(results, dict)
    # These are moved into the root
    assert results.get('format') == 'yaml'
    assert results.get('encoding') == 'latin-1'

    # But they also exist in the qsd location
    assert isinstance(results.get('qsd'), dict)
    assert results['qsd'].get('encoding') == 'latin-1'
    assert results['qsd'].get('format') == 'yaml'

    # Valid URL & Invalid Format
    results = ConfigBase.parse_url(
        url='file://relative/path?format=invalid&encoding=latin-1')
    assert isinstance(results, dict)
    # Only encoding is moved into the root
    assert 'format' not in results
    assert results.get('encoding') == 'latin-1'

    # But they will always exist in the qsd location
    assert isinstance(results.get('qsd'), dict)
    assert results['qsd'].get('encoding') == 'latin-1'
    assert results['qsd'].get('format') == 'invalid'


def test_config_base_config_parse_text():
    """
    API: ConfigBase.config_parse_text object

    """

    # Garbage Handling
    assert isinstance(ConfigBase.config_parse_text(object()), list)
    assert isinstance(ConfigBase.config_parse_text(None), list)
    assert isinstance(ConfigBase.config_parse_text(''), list)

    # Valid Configuration
    result = ConfigBase.config_parse_text("""
    # A comment line over top of a URL
    mailto://userb:pass@gmail.com

    # A line with mulitiple tag assignments to it
    taga,tagb=kde://
    """, asset=AppriseAsset())

    # We expect to parse 2 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0].tags) == 0

    # Our second element will have tags associated with it
    assert len(result[1].tags) == 2
    assert 'taga' in result[1].tags
    assert 'tagb' in result[1].tags

    # Here is a similar result set however this one has an invalid line
    # in it which invalidates the entire file
    result = ConfigBase.config_parse_text("""
    # A comment line over top of a URL
    mailto://userc:pass@gmail.com

    # A line with mulitiple tag assignments to it
    taga,tagb=windows://

    I am an invalid line that does not follow any of the Apprise file rules!
    """)

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # More invalid data
    result = ConfigBase.config_parse_text("""
    # An invalid URL
    invalid://user:pass@gmail.com

    # A tag without a url
    taga=

    # A very poorly structured url
    sns://:@/

    # Just 1 token provided
    sns://T1JJ3T3L2/
    """)

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # Here is an empty file
    result = ConfigBase.config_parse_text('')

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0


def test_config_base_config_parse_yaml():
    """
    API: ConfigBase.config_parse_yaml object

    """

    # general reference used below
    asset = AppriseAsset()

    # Garbage Handling
    assert isinstance(ConfigBase.config_parse_yaml(object()), list)
    assert isinstance(ConfigBase.config_parse_yaml(None), list)
    assert isinstance(ConfigBase.config_parse_yaml(''), list)

    # Invalid Version
    result = ConfigBase.config_parse_yaml("version: 2a", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid Syntax (throws a ScannerError)
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls
""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Missing url token
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # No urls defined
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid url defined
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

# Invalid URL definition; yet the answer to life at the same time
urls: 43
""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid url/schema
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
  - invalid://

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid url/schema
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
  - invalid://:
    - a: b

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid url/schema
    result = ConfigBase.config_parse_yaml("""
urls:
  - just some free text that isn't valid:
    - a garbage entry to go with it

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid url/schema
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
  - not even a proper url

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid url/schema
    result = ConfigBase.config_parse_yaml("""
# no lists... just no
urls: [milk, pumpkin pie, eggs, juice]

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Invalid url/schema
    result = ConfigBase.config_parse_yaml("""
urls:
  # a very invalid sns entry
  - sns://T1JJ3T3L2/
  - sns://:@/:
    - invalid: test
  - sns://T1JJ3T3L2/:
    - invalid: test

  # some strangness
  -
    -
      - test

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # Valid Configuration
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

#
# Define your notification urls:
#
urls:
  - pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b
  - mailto://test:password@gmail.com
""", asset=asset)

    # We expect to parse 2 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0].tags) == 0

    # Valid Configuration
    result = ConfigBase.config_parse_yaml("""
urls:
  - json://localhost:
    - tag: my-custom-tag, my-other-tag

  # How to stack multiple entries:
  - mailto://:
    - user: jeff
      pass: 123abc
      from: jeff@yahoo.ca

    - user: jack
      pass: pass123
      from: jack@hotmail.com

      # This is an illegal entry; the schema can not be changed
      schema: json

  # accidently left a colon at the end of the url; no problem
  # we'll accept it
  - mailto://oscar:pass@gmail.com:

  # A telegram entry (returns a None in parse_url())
  - tgram://invalid

""", asset=asset)

    # We expect to parse 4 entries from the above because the tgram:// entry
    # would have failed to be loaded
    assert isinstance(result, list)
    assert len(result) == 4
    assert len(result[0].tags) == 2

    # Global Tags
    result = ConfigBase.config_parse_yaml("""
# Global Tags stacked as a list
tag:
  - admin
  - devops

urls:
  - json://localhost
  - dbus://
""", asset=asset)

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2

    # all entries will have our global tags defined in them
    for entry in result:
        assert 'admin' in entry.tags
        assert 'devops' in entry.tags

    # Global Tags
    result = ConfigBase.config_parse_yaml("""
# Global Tags
tag: admin, devops

urls:
  # The following tags will get added to the global set
  - json://localhost:
    - tag: string-tag, my-other-tag, text

  # Tags can be presented in this list format too:
  - dbus://:
    - tag:
      - list-tag
      - dbus
""", asset=asset)

    # all entries will have our global tags defined in them
    for entry in result:
        assert 'admin' in entry.tags
        assert 'devops' in entry.tags

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2

    # json:// has 2 globals + 3 defined
    assert len(result[0].tags) == 5
    assert 'text' in result[0].tags

    # json:// has 2 globals + 2 defined
    assert len(result[1].tags) == 4
    assert 'list-tag' in result[1].tags

    # An invalid set of entries
    result = ConfigBase.config_parse_yaml("""
urls:
  # The following tags will get added to the global set
  - json://localhost:
    -
      -
        - entry
""", asset=asset)

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # An asset we'll manipulate
    asset = AppriseAsset()

    # Global Tags
    result = ConfigBase.config_parse_yaml("""
# Test the creation of our apprise asset object
asset:
  app_id: AppriseTest
  app_desc: Apprise Test Notifications
  app_url: http://nuxref.com

  # Support setting empty values
  image_url_mask:
  image_url_logo:

  image_path_mask: tmp/path

  # invalid entry
  theme:
    -
      -
        - entry

  # Now for some invalid entries
  invalid: entry
  __init__: can't be over-ridden
  nolists:
    - we don't support these entries
    - in the apprise object

urls:
  - json://localhost:
""", asset=asset)

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert len(result) == 1
    assert asset.app_id == "AppriseTest"
    assert asset.app_desc == "Apprise Test Notifications"
    assert asset.app_url == "http://nuxref.com"

    # the theme was not updated and remains the same as it was
    assert asset.theme == AppriseAsset().theme

    # Empty string assignment
    assert isinstance(asset.image_url_mask, six.string_types) is True
    assert asset.image_url_mask == ""
    assert isinstance(asset.image_url_logo, six.string_types) is True
    assert asset.image_url_logo == ""

    # For on-lookers looking through this file; here is a perfectly formatted
    # YAML configuration file for your reference so you can see it without
    # all of the errors like the ones identified above
    result = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed. Thus this is a
# completely optional field. It's a good idea to just add this line because it
# will help with future ambiguity (if it ever occurs).
version: 1

# Define an Asset object if you wish (Optional)
asset:
  app_id: AppriseTest
  app_desc: Apprise Test Notifications
  app_url: http://nuxref.com

# Optionally define some global tags to associate with ALL of your
# urls below.
tag: admin, devops

# Define your URLs (Mandatory!)
urls:
  # Either on-line each entry like this:
  - json://localhost

  # Or add a colon to the end of the URL where you can optionally provide
  # over-ride entries.  One of the most likely entry to be used here
  # is the tag entry.  This gets extended to the global tag (if defined)
  # above
  - xml://localhost:
    - tag: customer

  # The more elements you specify under a URL the more times the URL will
  # get replicated and used. Hence this entry actually could be considered
  # 2 URLs being called with just the destination email address changed:
  - mailto://george:password@gmail.com:
     - to: jason@hotmail.com
     - to: fred@live.com

  # Again... to re-iterate, the above mailto:// would actually fire two (2)
  # separate emails each with a different destination address specified.
  # Be careful when defining your arguments and differentiating between
  # when to use the dash (-) and when not to.  Each time you do, you will
  # cause another instance to be created.

  # Defining more then 1 element to a muti-set is easy, it looks like this:
  - mailto://jackson:abc123@hotmail.com:
     - to: jeff@gmail.com
       tag: jeff, customer

     - to: chris@yahoo.com
       tag: chris, customer
""", asset=asset)

    # okay, here is how we get our total based on the above (read top-down)
    # +1  json:// entry
    # +1  xml:// entry
    # +2  mailto:// entry to jason@hotmail.com and fred@live.com
    # +2  mailto:// entry to jeff@gmail.com and chris@yahoo.com
    # = 6
    assert len(result) == 6

    # all six entries will have our global tags defined in them
    for entry in result:
        assert 'admin' in entry.tags
        assert 'devops' in entry.tags

    # Entries can be directly accessed as they were added

    # our json:// had no additional tags added; so just the global ones
    # So just 2; admin and devops (these were already validated above in the
    # for loop
    assert len(result[0].tags) == 2

    # our xml:// object has 1 tag added (customer)
    assert len(result[1].tags) == 3
    assert 'customer' in result[1].tags

    # You get the idea, here is just a direct mapping to the remaining entries
    # in the same order they appear above
    assert len(result[2].tags) == 2
    assert len(result[3].tags) == 2

    assert len(result[4].tags) == 4
    assert 'customer' in result[4].tags
    assert 'jeff' in result[4].tags

    assert len(result[5].tags) == 4
    assert 'customer' in result[5].tags
    assert 'chris' in result[5].tags


def test_config_matrix_dynamic_importing(tmpdir):
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
class ConfigBadFile1(object):
    pass""")

    # No class of the same name
    base.join('ConfigBadFile2.py').write(
        """
class BadClassName(object):
    pass""")

    # Exception thrown
    base.join('ConfigBadFile3.py').write("""raise ImportError()""")

    # Utilizes a schema:// already occupied (as string)
    base.join('ConfigGoober.py').write(
        """
from apprise import ConfigBase
class ConfigGoober(ConfigBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol (used by ConfigMail)
    protocol = 'http'

    # The default secure protocol (used by ConfigMail)
    secure_protocol = 'https'""")

    # Utilizes a schema:// already occupied (as tuple)
    base.join('ConfigBugger.py').write("""
from apprise import ConfigBase
class ConfigBugger(ConfigBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol (used by ConfigMail), the other
    # isn't
    protocol = ('http', 'bugger-test' )

    # The default secure protocol (used by ConfigMail), the other isn't
    secure_protocol = ('https', 'bugger-tests')""")

    __load_matrix(path=str(base), name=module_name)
