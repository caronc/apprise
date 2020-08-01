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

import os
import sys
import pytest
import apprise

try:
    # Python v3.4+
    from importlib import reload
except ImportError:
    try:
        # Python v3.0-v3.3
        from imp import reload
    except ImportError:
        # Python v2.7
        pass

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="requires cryptography")
def test_simplepush_plugin(tmpdir):
    """
    API: NotifySimplePush Plugin()

    """
    suite = tmpdir.mkdir("simplepush")
    suite.join("__init__.py").write('')
    module_name = 'cryptography'
    suite.join("{}.py".format(module_name)).write('raise ImportError()')

    # Update our path to point to our new test suite
    sys.path.insert(0, str(suite))

    for name in list(sys.modules.keys()):
        if name.startswith('{}.'.format(module_name)):
            del sys.modules[name]
    del sys.modules[module_name]

    # The following libraries need to be reloaded to prevent
    #  TypeError: super(type, obj): obj must be an instance or subtype of type
    #  This is better explained in this StackOverflow post:
    #     https://stackoverflow.com/questions/31363311/\
    #       any-way-to-manually-fix-operation-of-\
    #          super-after-ipython-reload-avoiding-ty
    #
    reload(sys.modules['apprise.plugins.NotifySimplePush'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # Without the cryptography library objects can still be instantiated
    # however notifications will fail
    obj = apprise.Apprise.instantiate('spush://salt:pass@valid_api_key')
    assert obj is not None

    # We can't notify with a user/pass combo and no cryptography library
    assert obj.notify(
        title="test message title", body="message body") is False

    # Tidy-up / restore things to how they were
    os.unlink(str(suite.join("{}.py".format(module_name))))
    reload(sys.modules['apprise.plugins.NotifySimplePush'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])
