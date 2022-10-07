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
import types
from unittest import mock

import apprise
from helpers import module_reload
from apprise.plugins.NotifyGnome import GnomeUrgency

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_plugin_gnome_general():
    """
    NotifyGnome() General Checks

    """

    # Our module base
    gi_name = 'gi'

    # First we do an import without the gi library available to ensure
    # we can handle cases when the library simply isn't available

    if gi_name in sys.modules:
        # Test cases where the gi library exists; we want to remove it
        # for the purpose of testing and capture the handling of the
        # library when it is missing
        del sys.modules[gi_name]
        module_reload('NotifyGnome')

    # We need to fake our gnome environment for testing purposes since
    # the gi library isn't available in Travis CI
    gi = types.ModuleType(gi_name)
    gi.repository = types.ModuleType(gi_name + '.repository')
    gi.module = types.ModuleType(gi_name + '.module')

    mock_pixbuf = mock.Mock()
    mock_notify = mock.Mock()

    gi.repository.GdkPixbuf = \
        types.ModuleType(gi_name + '.repository.GdkPixbuf')
    gi.repository.GdkPixbuf.Pixbuf = mock_pixbuf
    gi.repository.Notify = mock.Mock()
    gi.repository.Notify.init.return_value = True
    gi.repository.Notify.Notification = mock_notify

    # Emulate require_version function:
    gi.require_version = mock.Mock(
        name=gi_name + '.require_version')

    # Force the fake module to exist
    sys.modules[gi_name] = gi
    sys.modules[gi_name + '.repository'] = gi.repository
    sys.modules[gi_name + '.repository.Notify'] = gi.repository.Notify

    # Notify Object
    notify_obj = mock.Mock()
    notify_obj.set_urgency.return_value = True
    notify_obj.set_icon_from_pixbuf.return_value = True
    notify_obj.set_image_from_pixbuf.return_value = True
    notify_obj.show.return_value = True
    mock_notify.new.return_value = notify_obj
    mock_pixbuf.new_from_file.return_value = True
    module_reload('NotifyGnome')

    # Create our instance
    obj = apprise.Apprise.instantiate('gnome://', suppress_exceptions=False)
    assert obj is not None

    # Set our duration to 0 to speed up timeouts (for testing)
    obj.duration = 0

    # Check that it found our mocked environments
    assert obj.enabled is True

    # Test url() call
    assert isinstance(obj.url(), str) is True

    # test notifications
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    # test notification without a title
    assert obj.notify(title='', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'gnome://_/?image=True', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'gnome://_/?image=False', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    # Test Priority (alias of urgency)
    obj = apprise.Apprise.instantiate(
        'gnome://_/?priority=invalid', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.urgency == 1
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'gnome://_/?priority=high', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.urgency == 2
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'gnome://_/?priority=2', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.urgency == 2
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    # Test Urgeny
    obj = apprise.Apprise.instantiate(
        'gnome://_/?urgency=invalid', suppress_exceptions=False)
    assert obj.urgency == 1
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'gnome://_/?urgency=high', suppress_exceptions=False)
    assert obj.urgency == 2
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'gnome://_/?urgency=2', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyGnome) is True
    assert obj.urgency == 2
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    # Test configuration parsing
    content = """
    urls:
      - gnome://:
          - priority: 0
            tag: gnome_int low
          - priority: "0"
            tag: gnome_str_int low
          - priority: low
            tag: gnome_str low
          - urgency: 0
            tag: gnome_int low
          - urgency: "0"
            tag: gnome_str_int low
          - urgency: low
            tag: gnome_str low

          # These will take on normal (default) urgency
          - priority: invalid
            tag: gnome_invalid
          - urgency: invalid
            tag: gnome_invalid

      - gnome://:
          - priority: 2
            tag: gnome_int high
          - priority: "2"
            tag: gnome_str_int high
          - priority: high
            tag: gnome_str high
          - urgency: 2
            tag: gnome_int high
          - urgency: "2"
            tag: gnome_str_int high
          - urgency: high
            tag: gnome_str high
    """

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 14 servers from that
    # 6x low
    # 6x high
    # 2x invalid (so takes on normal urgency)
    assert len(ac.servers()) == 14
    assert len(aobj) == 14
    assert len([x for x in aobj.find(tag='low')]) == 6
    for s in aobj.find(tag='low'):
        assert s.urgency == GnomeUrgency.LOW

    assert len([x for x in aobj.find(tag='high')]) == 6
    for s in aobj.find(tag='high'):
        assert s.urgency == GnomeUrgency.HIGH

    assert len([x for x in aobj.find(tag='gnome_str')]) == 4
    assert len([x for x in aobj.find(tag='gnome_str_int')]) == 4
    assert len([x for x in aobj.find(tag='gnome_int')]) == 4

    assert len([x for x in aobj.find(tag='gnome_invalid')]) == 2
    for s in aobj.find(tag='gnome_invalid'):
        assert s.urgency == GnomeUrgency.NORMAL

    # Test our loading of our icon exception; it will still allow the
    # notification to be sent
    mock_pixbuf.new_from_file.side_effect = AttributeError()
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True
    # Undo our change
    mock_pixbuf.new_from_file.side_effect = None

    # Test our exception handling during initialization
    sys.modules['gi.repository.Notify']\
        .Notification.new.return_value = None
    sys.modules['gi.repository.Notify']\
        .Notification.new.side_effect = AttributeError()
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is False

    # Undo our change
    sys.modules['gi.repository.Notify']\
        .Notification.new.side_effect = None

    # Toggle our testing for when we can't send notifications because the
    # package has been made unavailable to us
    obj.enabled = False
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is False

    # Test the setting of a the urgency (through priority keyword)
    apprise.plugins.NotifyGnome(priority=0)

    # Verify this all works in the event a ValueError is also thronw
    # out of the call to gi.require_version()

    # Emulate require_version function:
    gi.require_version.side_effect = ValueError()
    module_reload('NotifyGnome')

    # We can now no longer load our instance
    # The object internally is marked disabled
    obj = apprise.Apprise.instantiate('gnome://', suppress_exceptions=False)
    assert obj is None
