# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
import builtins
import contextlib

from _pytest.monkeypatch import MonkeyPatch


@contextlib.contextmanager
def emulate_import_error(*module_names, package=None):
    """
    Emulate an `ImportError` on a list of module names.

    http://materials-scientist.com/blog/2021/02/11/mocking-failing-module-import-python/
    """

    real_import = builtins.__import__

    def import_hook(name, globals, *args, **kwargs):
        if name in module_names:
            pkg = globals["__package__"]
            if package is None or package == pkg:
                raise ImportError(f"Mocked import error {name}")
        return real_import(name, globals, *args, **kwargs)

    with MonkeyPatch().context() as m:
        m.setattr(builtins, '__import__', import_hook)
        yield
