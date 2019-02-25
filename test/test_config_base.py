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

from apprise.AppriseAsset import AppriseAsset
from apprise.config.ConfigBase import ConfigBase

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

    # Notify format types are not the same as ConfigBase ones
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
