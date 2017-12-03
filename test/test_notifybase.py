# -*- coding: utf-8 -*-
#
# NotifyBase Unit Tests
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

from apprise.plugins.NotifyBase import NotifyBase
from apprise import NotifyType
from apprise import NotifyImageSize
from timeit import default_timer


def test_notify_base():
    """
    API: NotifyBase() object

    """

    # invalid types throw exceptions
    try:
        nb = NotifyBase(notify_format='invalid')
        # We should never reach here as an exception should be thrown
        assert(False)

    except TypeError:
        assert(True)

    try:
        nb = NotifyBase(image_size='invalid')
        # We should never reach here as an exception should be thrown
        assert(False)

    except TypeError:
        assert(True)

    # Bad port information
    nb = NotifyBase(port='invalid')
    assert nb.port is None

    nb = NotifyBase(port=10)
    assert nb.port == 10

    # Throttle overrides..
    nb = NotifyBase(throttle=0)
    start_time = default_timer()
    nb.throttle()
    elapsed = default_timer() - start_time
    # Should be a very fast response time since we set it to zero but we'll
    # check for less then 500 to be fair as some testing systems may be slower
    # then other
    assert elapsed < 0.5

    start_time = default_timer()
    nb.throttle(1.0)
    elapsed = default_timer() - start_time
    # Should be a very fast response time since we set it to zero but we'll
    # check for less then 500 to be fair as some testing systems may be slower
    # then other
    assert elapsed < 1.5

    # our NotifyBase wasn't initialized with an ImageSize so this will fail
    assert nb.image_url(notify_type=NotifyType.INFO) is None
    assert nb.image_path(notify_type=NotifyType.INFO) is None
    assert nb.image_raw(notify_type=NotifyType.INFO) is None

    # Create an object with an ImageSize loaded into it
    nb = NotifyBase(image_size=NotifyImageSize.XY_256)

    # We'll get an object thi time around
    assert nb.image_url(notify_type=NotifyType.INFO) is not None
    assert nb.image_path(notify_type=NotifyType.INFO) is not None
    assert nb.image_raw(notify_type=NotifyType.INFO) is not None

    # But we will not get a response with an invalid notification type
    assert nb.image_url(notify_type='invalid') is None
    assert nb.image_path(notify_type='invalid') is None
    assert nb.image_raw(notify_type='invalid') is None

    # Static function testing
    assert NotifyBase.escape_html("<content>'\t \n</content>") == \
        '&lt;content&gt;&apos;&emsp;&nbsp;\n&lt;/content&gt;'

    assert NotifyBase.escape_html(
        "<content>'\t \n</content>", convert_new_lines=True) == \
        '&lt;content&gt;&apos;&emsp;&nbsp;&lt;br/&gt;&lt;/content&gt;'

    assert NotifyBase.split_path(
        '/path/?name=Dr%20Disrespect', unquote=False) == \
        ['path', '?name=Dr%20Disrespect']

    assert NotifyBase.split_path(
        '/path/?name=Dr%20Disrespect', unquote=True) == \
        ['path', '?name=Dr', 'Disrespect']

    assert NotifyBase.is_email('test@gmail.com') is True
    assert NotifyBase.is_email('invalid.com') is False


def test_notify_base_urls():
    """
    API: NotifyBase() URLs

    """

    # Test verify switch whih is used as part of the SSL Verification
    # by default all SSL sites are verified unless this flag is set to
    # something like 'No', 'False', 'Disabled', etc.  Boolean values are
    # pretty forgiving.
    results = NotifyBase.parse_url('https://localhost:8080/?verify=No')
    assert 'verify' in results
    assert results['verify'] is False

    results = NotifyBase.parse_url('https://localhost:8080/?verify=Yes')
    assert 'verify' in results
    assert results['verify'] is True

    # The default is to verify
    results = NotifyBase.parse_url('https://localhost:8080')
    assert 'verify' in results
    assert results['verify'] is True

    # Password Handling

    # pass keyword over-rides default password
    results = NotifyBase.parse_url('https://user:pass@localhost')
    assert 'password' in results
    assert results['password'] == "pass"

    # pass keyword over-rides default password
    results = NotifyBase.parse_url(
        'https://user:pass@localhost?pass=newpassword')
    assert 'password' in results
    assert results['password'] == "newpassword"

    # User Handling

    # user keyword over-rides default password
    results = NotifyBase.parse_url('https://user:pass@localhost')
    assert 'user' in results
    assert results['user'] == "user"

    # user keyword over-rides default password
    results = NotifyBase.parse_url(
        'https://user:pass@localhost?user=newuser')
    assert 'user' in results
    assert results['user'] == "newuser"
