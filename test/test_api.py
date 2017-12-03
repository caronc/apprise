# -*- coding: utf-8 -*-
#
# Apprise and AppriseAsset Unit Tests
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

from __future__ import print_function
from __future__ import unicode_literals
from os import chmod
from os.path import dirname
from apprise import Apprise
from apprise import AppriseAsset
from apprise.Apprise import SCHEMA_MAP
from apprise import NotifyBase
from apprise import NotifyType
from apprise import NotifyImageSize
from apprise.Apprise import __load_matrix


def test_apprise():
    """
    API: Apprise() object

    """
    # Caling load matix a second time which is an internal function causes it
    # to skip over content already loaded into our matrix and thefore accesses
    # other if/else parts of the code that aren't otherwise called
    __load_matrix()

    a = Apprise()

    # no items
    assert(len(a) == 0)

    # Create an Asset object
    asset = AppriseAsset(theme='default')

    # We can load the device using our asset
    a = Apprise(asset=asset)

    # We can load our servers up front as well
    servers = [
        'faast://abcdefghijklmnop-abcdefg',
        'kodi://kodi.server.local',
        'palot://1f418df7577e32b89ac6511f2eb9aa68',
    ]

    a = Apprise(servers=servers)

    # 3 servers loaded
    assert(len(a) == 3)

    # We can add another server
    assert(
        a.add('mmosts://mattermost.server.local/'
              '3ccdd113474722377935511fc85d3dd4') is True)
    assert(len(a) == 4)

    # We can empty our set
    a.clear()
    assert(len(a) == 0)

    # An invalid schema
    assert(
        a.add('this is not a parseable url at all') is False)
    assert(len(a) == 0)

    # An unsupported schema
    assert(
        a.add('invalid://we.just.do.not.support.this.plugin.type') is False)
    assert(len(a) == 0)

    # A poorly formatted URL
    assert(
        a.add('json://user:@@@:bad?no.good') is False)
    assert(len(a) == 0)

    # Add a server with our asset we created earlier
    assert(
        a.add('mmosts://mattermost.server.local/'
              '3ccdd113474722377935511fc85d3dd4', asset=asset) is True)

    # Clear our server listings again
    a.clear()

    # No servers to notify
    assert(a.notify(title="my title", body="my body") is False)

    class BadNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(BadNotification, self).__init__()

            # We fail whenever we're initialized
            raise TypeError()

    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(GoodNotification, self).__init__()

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

    # Store our bad notification in our schema map
    SCHEMA_MAP['bad'] = BadNotification

    # Store our good notification in our schema map
    SCHEMA_MAP['good'] = GoodNotification

    # Just to explain what is happening here, we would have parsed the
    # url properly but failed when we went to go and create an instance
    # of it.
    assert(a.add('bad://localhost') is False)
    assert(len(a) == 0)

    assert(a.add('good://localhost') is True)
    assert(len(a) == 1)

    # Bad Notification Type is still allowed as it is presumed the user
    # know's what their doing
    assert(a.notify(
        title="my title", body="my body", notify_type='bad') is True)

    # No Title/Body combo's
    assert(a.notify(title=None, body=None) is False)
    assert(a.notify(title='', body=None) is False)
    assert(a.notify(title=None, body='') is False)

    # As long as one is present, we're good
    assert(a.notify(title=None, body='present') is True)
    assert(a.notify(title='present', body=None) is True)
    assert(a.notify(title="present", body="present") is True)

    # Clear our server listings again
    a.clear()

    class ThrowNotification(NotifyBase):
        def notify(self, **kwargs):
            # Pretend everything is okay
            raise TypeError()

    class FailNotification(NotifyBase):

        def notify(self, **kwargs):
            # Pretend everything is okay
            return False

    # Store our bad notification in our schema map
    SCHEMA_MAP['throw'] = ThrowNotification

    # Store our good notification in our schema map
    SCHEMA_MAP['fail'] = FailNotification

    assert(a.add('throw://localhost') is True)
    assert(a.add('fail://localhost') is True)
    assert(len(a) == 2)

    # Test when our notify both throws an exception and or just
    # simply returns False
    assert(a.notify(title="present", body="present") is False)

    # Test instantiating a plugin
    class ThrowInstantiateNotification(NotifyBase):
        def __init__(self, **kwargs):
            # Pretend everything is okay
            raise TypeError()
    SCHEMA_MAP['throw'] = ThrowInstantiateNotification

    # Reset our object
    a.clear()
    assert(len(a) == 0)

    # Instantiate a good object
    plugin = a.instantiate('good://localhost')
    assert(isinstance(plugin, NotifyBase))

    # We an add already substatiated instances into our Apprise object
    a.add(plugin)
    assert(len(a) == 1)

    # Reset our object again
    a.clear()
    try:
        a.instantiate('throw://localhost', suppress_exceptions=False)
        assert(False)

    except TypeError:
        assert(True)
    assert(len(a) == 0)

    assert(a.instantiate(
        'throw://localhost', suppress_exceptions=True) is None)
    assert(len(a) == 0)


def test_apprise_asset(tmpdir):
    """
    API: AppriseAsset() object

    """
    a = AppriseAsset(theme=None)
    # Default theme
    assert(a.theme == 'default')

    a = AppriseAsset(
        theme='dark',
        image_path_mask='/{THEME}/{TYPE}-{XY}.png',
        image_url_mask='http://localhost/{THEME}/{TYPE}-{XY}.png',
    )

    a.default_html_color = '#abcabc'
    a.html_notify_map[NotifyType.INFO] = '#aaaaaa'

    assert(a.html_color('invalid') == '#abcabc')
    assert(a.html_color(NotifyType.INFO) == '#aaaaaa')

    assert(a.image_url(NotifyType.INFO, NotifyImageSize.XY_256) ==
           'http://localhost/dark/info-256x256.png')

    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=False) == '/dark/info-256x256.png')

    # This path doesn't exist so image_raw will fail (since we just
    # randompyl picked it for testing)
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None)

    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is None)

    # Create a new object (with our default settings)
    a = AppriseAsset()

    # Our default configuration can access our file
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None)

    # Create a temporary directory
    sub = tmpdir.mkdir("great.theme")

    # Write a file
    sub.join("{0}-{1}.png".format(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
    )).write("the content doesn't matter for testing.")

    # Create an asset that will reference our file we just created
    a = AppriseAsset(
        theme='great.theme',
        image_path_mask='%s/{THEME}/{TYPE}-{XY}.png' % dirname(sub.strpath),
    )

    # We'll be able to read file we just created
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None)

    # We can retrieve the filename at this point even with must_exist set
    # to True
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    # If we make the file un-readable however, we won't be able to read it
    # This test is just showing that we won't throw an exception
    chmod(dirname(sub.strpath), 0o000)
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None)

    # Our path doesn't exist anymore using this logic
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is None)

    # Return our permission so we don't have any problems with our cleanup
    chmod(dirname(sub.strpath), 0o700)

    # Our content is retrivable again
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None)

    # our file path is accessible again too
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    # We do the same test, but set the permission on the file
    chmod(a.image_path(NotifyType.INFO, NotifyImageSize.XY_256), 0o000)

    # our path will still exist in this case
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    # but we will not be able to open it
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None)

    # Restore our permissions
    chmod(a.image_path(NotifyType.INFO, NotifyImageSize.XY_256), 0o640)
