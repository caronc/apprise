# Copyright: 2013 Paul Traylor
# These sources are released under the terms of the MIT license: see LICENSE

"""
Python2.5 and Python3.3 compatibility shim

Heavily inspirted by the "six" library.
https://pypi.python.org/pypi/six
"""

import sys

PY3 = sys.version_info[0] == 3

if PY3:
	def b(s):
		if isinstance(s, bytes):
			return s
		return s.encode('utf8', 'replace')

	def u(s):
		if isinstance(s, bytes):
			return s.decode('utf8', 'replace')
		return s

	from io import BytesIO as StringIO
	from configparser import RawConfigParser
else:
	def b(s):
		if isinstance(s, unicode):
			return s.encode('utf8', 'replace')
		return s

	def u(s):
		if isinstance(s, unicode):
			return s
		if isinstance(s, int):
			s = str(s)
		return unicode(s, "utf8", "replace")

	from StringIO import StringIO
	from ConfigParser import RawConfigParser

b.__doc__ = "Ensure we have a byte string"
u.__doc__ = "Ensure we have a unicode string"
