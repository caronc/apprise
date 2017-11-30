"""API properties.

"""

from __future__ import print_function
from __future__ import unicode_literals
from apprise import Apprise
from apprise import AppriseAsset
from apprise.Apprise import SCHEMA_MAP
from apprise.plugins.NotifyBase import NotifyBase
from apprise import NotifyType
from apprise import NotifyImageSize


def test_apprise():
    """
    API: Apprise() object

    """
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


def test_apprise_asset():
    """
    API: AppriseAsset() object

    """
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
