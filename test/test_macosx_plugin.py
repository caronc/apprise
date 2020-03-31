# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

import os
import six
import mock

import apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@mock.patch('subprocess.Popen')
@mock.patch('platform.system')
@mock.patch('platform.mac_ver')
def test_macosx_plugin(mock_macver, mock_system, mock_popen, tmpdir):
    """
    API: NotifyMacOSX Plugin()

    """

    # Create a temporary binary file we can reference
    script = tmpdir.join("terminal-notifier")
    script.write('')
    # Give execute bit
    os.chmod(str(script), 0o755)
    # Point our object to our new temporary existing file
    apprise.plugins.NotifyMacOSX.notify_path = str(script)
    mock_cmd_response = mock.Mock()

    # Set a successful response
    mock_cmd_response.returncode = 0

    # Simulate a Mac Environment
    mock_system.return_value = 'Darwin'
    mock_macver.return_value = ('10.8', ('', '', ''), '')
    mock_popen.return_value = mock_cmd_response

    obj = apprise.Apprise.instantiate(
        'macosx://_/?image=True', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is True

    # Test url() call
    assert isinstance(obj.url(), six.string_types) is True

    # test notifications
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    # test notification without a title
    assert obj.notify(title='', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'macosx://_/?image=True', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'macosx://_/?image=False', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is True
    assert isinstance(obj.url(), six.string_types) is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    # Test Sound
    obj = apprise.Apprise.instantiate(
        'macosx://_/?sound=default', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is True
    assert obj.sound == 'default'
    assert isinstance(obj.url(), six.string_types) is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is True

    # Now test cases where our environment isn't set up correctly
    # In this case we'll simulate a situation where our binary isn't
    # executable
    os.chmod(str(script), 0o644)
    obj = apprise.Apprise.instantiate(
        'macosx://_/?sound=default', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is False
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is False
    # Restore permission
    os.chmod(str(script), 0o755)

    # Test case where we simply aren't on a mac
    mock_system.return_value = 'Linux'
    obj = apprise.Apprise.instantiate(
        'macosx://_/?sound=default', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is False
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is False
    # Restore mac environment
    mock_system.return_value = 'Darwin'

    # Now we must be Mac OS v10.8 or higher... Test cases where we aren't
    mock_macver.return_value = ('10.7', ('', '', ''), '')
    obj = apprise.Apprise.instantiate(
        'macosx://_/?sound=default', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is False
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is False
    # Restore valid mac environment
    mock_macver.return_value = ('10.8', ('', '', ''), '')

    mock_macver.return_value = ('9.12', ('', '', ''), '')
    obj = apprise.Apprise.instantiate(
        'macosx://_/?sound=default', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is False
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is False
    # Restore valid mac environment
    mock_macver.return_value = ('10.8', ('', '', ''), '')

    # Test cases where the script just flat out fails
    mock_cmd_response.returncode = 1
    obj = apprise.Apprise.instantiate(
        'macosx://', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMacOSX) is True
    assert obj._enabled is True
    assert obj.notify(title='title', body='body',
                      notify_type=apprise.NotifyType.INFO) is False
    # Restore script return value
    mock_cmd_response.returncode = 1
