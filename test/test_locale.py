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

import mock
import ctypes

from apprise import AppriseLocale

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


@mock.patch('gettext.install')
def test_apprise_locale(mock_gettext_install):
    """
    API: Test apprise locale object
    """
    lazytrans = AppriseLocale.LazyTranslation('Token')
    assert str(lazytrans) == 'Token'


@mock.patch('gettext.install')
def test_gettext_init(mock_gettext_install):
    """
    API: Mock Gettext init
    """
    mock_gettext_install.side_effect = ImportError()
    # Test our fall back to not supporting translations
    reload(AppriseLocale)

    # Objects can still be created
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # restore the object
    mock_gettext_install.side_effect = None
    reload(AppriseLocale)


@mock.patch('gettext.translation')
def test_gettext_translations(mock_gettext_trans):
    """
    API: Apprise() Gettext translations

    """

    mock_gettext_trans.side_effect = IOError()

    # This throws internally but we handle it gracefully
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # This throws internally but we handle it gracefully
    AppriseLocale.AppriseLocale(language="fr")


@mock.patch('gettext.translation')
def test_gettext_installs(mock_gettext_trans):
    """
    API: Apprise() Gettext install

    """

    mock_lang = mock.Mock()
    mock_lang.install.return_value = True
    mock_gettext_trans.return_value = mock_lang

    # This throws internally but we handle it gracefully
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # This throws internally but we handle it gracefully
    AppriseLocale.AppriseLocale(language="fr")

    # Force a few different languages
    al._gtobjs['en'] = mock_lang
    al._gtobjs['es'] = mock_lang
    al.lang = 'en'

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    with al.lang_at('es'):
        # functions still behave as normal
        pass

    with al.lang_at('fr'):
        # functions still behave as normal
        pass


@mock.patch('locale.getdefaultlocale')
def test_detect_language(mock_getlocale):
    """
    API: Apprise() Detect language

    """

    if not hasattr(ctypes, 'windll'):
        windll = mock.Mock()
        # 4105 = en_CA
        windll.kernel32.GetUserDefaultUILanguage.return_value = 4105
        setattr(ctypes, 'windll', windll)

    # The below accesses the windows fallback code
    assert AppriseLocale.AppriseLocale.detect_language() == 'en'

    assert AppriseLocale.AppriseLocale\
        .detect_language(detect_fallback=False) is None

    # Handle case where getdefaultlocale() can't be detected
    mock_getlocale.return_value = None
    delattr(ctypes, 'windll')
    assert AppriseLocale.AppriseLocale.detect_language() is None

    # if detect_language and windows env fail us, then we don't
    # set up a default language on first load
    AppriseLocale.AppriseLocale()
