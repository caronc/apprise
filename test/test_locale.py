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
from unittest import mock

import ctypes

from apprise import AppriseLocale
from apprise.utils import environ
from importlib import reload


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


def test_detect_language_windows_users():
    """
    API: Apprise() Detect language

    """

    if not hasattr(ctypes, 'windll'):
        windll = mock.Mock()
        # 4105 = en_CA
        windll.kernel32.GetUserDefaultUILanguage.return_value = 4105
        setattr(ctypes, 'windll', windll)

    # The below accesses the windows fallback code
    with environ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG="en_CA"):
        assert AppriseLocale.AppriseLocale.detect_language() == 'en'

    assert AppriseLocale.AppriseLocale\
        .detect_language(detect_fallback=False) is None

    # 0 = IndexError
    windll.kernel32.GetUserDefaultUILanguage.return_value = 0
    setattr(ctypes, 'windll', windll)
    with environ('LANG', 'LC_ALL', 'LC_CTYPE', LANGUAGE="en_CA"):
        assert AppriseLocale.AppriseLocale.detect_language() == 'en'

    # The below accesses the windows fallback code and fail
    # then it will resort to the environment variables
    with environ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE'):
        # Language can't be detected
        assert AppriseLocale.AppriseLocale.detect_language() is None

    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG="fr_CA"):
        # Detect french language
        assert AppriseLocale.AppriseLocale.detect_language() == 'fr'

    # The following unsets all environment variables and sets LC_CTYPE
    # This was causing Python 2.7 to internally parse UTF-8 as an invalid
    # locale and throw an uncaught ValueError; Python v2 support has been
    # dropped, but just to ensure this issue does not come back, we keep
    # this test:
    with environ(*list(os.environ.keys()), LC_CTYPE="UTF-8"):
        assert AppriseLocale.AppriseLocale.detect_language() is None

    # Test with absolutely no environment variables what-so-ever
    with environ(*list(os.environ.keys())):
        assert AppriseLocale.AppriseLocale.detect_language() is None

    # Tidy
    delattr(ctypes, 'windll')


@mock.patch('locale.getdefaultlocale')
def test_detect_language_defaultlocale(mock_getlocale):
    """
    API: Apprise() Default locale detection

    """
    # Handle case where getdefaultlocale() can't be detected
    mock_getlocale.return_value = None
    assert AppriseLocale.AppriseLocale.detect_language() is None

    # if detect_language and windows env fail us, then we don't
    # set up a default language on first load
    AppriseLocale.AppriseLocale()
