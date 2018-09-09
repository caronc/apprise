# Copyright: 2013 Paul Traylor
# These sources are released under the terms of the MIT license: see LICENSE

import hashlib
import re
import time

from . import shim
from . import errors as errors

__all__ = [
	'GNTPRegister',
	'GNTPNotice',
	'GNTPSubscribe',
	'GNTPOK',
	'GNTPError',
	'parse_gntp',
]

#GNTP/<version> <messagetype> <encryptionAlgorithmID>[:<ivValue>][ <keyHashAlgorithmID>:<keyHash>.<salt>]
GNTP_INFO_LINE = re.compile(
	r'GNTP/(?P<version>\d+\.\d+) (?P<messagetype>REGISTER|NOTIFY|SUBSCRIBE|\-OK|\-ERROR)' +
	r' (?P<encryptionAlgorithmID>[A-Z0-9]+(:(?P<ivValue>[A-F0-9]+))?) ?' +
	r'((?P<keyHashAlgorithmID>[A-Z0-9]+):(?P<keyHash>[A-F0-9]+).(?P<salt>[A-F0-9]+))?\r\n',
	re.IGNORECASE
)

GNTP_INFO_LINE_SHORT = re.compile(
	r'GNTP/(?P<version>\d+\.\d+) (?P<messagetype>REGISTER|NOTIFY|SUBSCRIBE|\-OK|\-ERROR)',
	re.IGNORECASE
)

GNTP_HEADER = re.compile(r'([\w-]+):(.+)')

GNTP_EOL = shim.b('\r\n')
GNTP_SEP = shim.b(': ')


class _GNTPBuffer(shim.StringIO):
	"""GNTP Buffer class"""
	def writeln(self, value=None):
		if value:
			self.write(shim.b(value))
		self.write(GNTP_EOL)

	def writeheader(self, key, value):
		if not isinstance(value, str):
			value = str(value)
		self.write(shim.b(key))
		self.write(GNTP_SEP)
		self.write(shim.b(value))
		self.write(GNTP_EOL)


class _GNTPBase(object):
	"""Base initilization

	:param string messagetype: GNTP Message type
	:param string version: GNTP Protocol version
	:param string encription: Encryption protocol
	"""
	def __init__(self, messagetype=None, version='1.0', encryption=None):
		self.info = {
			'version': version,
			'messagetype': messagetype,
			'encryptionAlgorithmID': encryption
		}
		self.hash_algo = {
			'MD5': hashlib.md5,
			'SHA1': hashlib.sha1,
			'SHA256': hashlib.sha256,
			'SHA512': hashlib.sha512,
		}	
		self.headers = {}
		self.resources = {}

	def __str__(self):
		return self.encode()

	def _parse_info(self, data):
		"""Parse the first line of a GNTP message to get security and other info values

		:param string data: GNTP Message
		:return dict: Parsed GNTP Info line
		"""

		match = GNTP_INFO_LINE.match(data)

		if not match:
			raise errors.ParseError('ERROR_PARSING_INFO_LINE')

		info = match.groupdict()
		if info['encryptionAlgorithmID'] == 'NONE':
			info['encryptionAlgorithmID'] = None

		return info

	def set_password(self, password, encryptAlgo='MD5'):
		"""Set a password for a GNTP Message

		:param string password: Null to clear password
		:param string encryptAlgo: Supports MD5, SHA1, SHA256, SHA512
		"""
		if not password:
			self.info['encryptionAlgorithmID'] = None
			self.info['keyHashAlgorithm'] = None
			return

		self.password = shim.b(password)
		self.encryptAlgo = encryptAlgo.upper()

		if not self.encryptAlgo in self.hash_algo:
			raise errors.UnsupportedError('INVALID HASH "%s"' % self.encryptAlgo)

		hashfunction = self.hash_algo.get(self.encryptAlgo)

		password = password.encode('utf8')
		seed = time.ctime().encode('utf8')
		salt = hashfunction(seed).hexdigest()
		saltHash = hashfunction(seed).digest()
		keyBasis = password + saltHash
		key = hashfunction(keyBasis).digest()
		keyHash = hashfunction(key).hexdigest()

		self.info['keyHashAlgorithmID'] = self.encryptAlgo
		self.info['keyHash'] = keyHash.upper()
		self.info['salt'] = salt.upper()

	def _decode_hex(self, value):
		"""Helper function to decode hex string to `proper` hex string

		:param string value: Human readable hex string
		:return string: Hex string
		"""
		result = ''
		for i in range(0, len(value), 2):
			tmp = int(value[i:i + 2], 16)
			result += chr(tmp)
		return result

	def _decode_binary(self, rawIdentifier, identifier):
		rawIdentifier += '\r\n\r\n'
		dataLength = int(identifier['Length'])
		pointerStart = self.raw.find(rawIdentifier) + len(rawIdentifier)
		pointerEnd = pointerStart + dataLength
		data = self.raw[pointerStart:pointerEnd]
		if not len(data) == dataLength:
			raise errors.ParseError('INVALID_DATA_LENGTH Expected: %s Recieved %s' % (dataLength, len(data)))
		return data

	def _validate_password(self, password):
		"""Validate GNTP Message against stored password"""
		self.password = password
		if password is None:
			raise errors.AuthError('Missing password')
		keyHash = self.info.get('keyHash', None)
		if keyHash is None and self.password is None:
			return True
		if keyHash is None:
			raise errors.AuthError('Invalid keyHash')
		if self.password is None:
			raise errors.AuthError('Missing password')

		keyHashAlgorithmID = self.info.get('keyHashAlgorithmID','MD5')

		password = self.password.encode('utf8')
		saltHash = self._decode_hex(self.info['salt'])

		keyBasis = password + saltHash
		self.key = self.hash_algo[keyHashAlgorithmID](keyBasis).digest()
		keyHash = self.hash_algo[keyHashAlgorithmID](self.key).hexdigest()

		if not keyHash.upper() == self.info['keyHash'].upper():
			raise errors.AuthError('Invalid Hash')
		return True

	def validate(self):
		"""Verify required headers"""
		for header in self._requiredHeaders:
			if not self.headers.get(header, False):
				raise errors.ParseError('Missing Notification Header: ' + header)

	def _format_info(self):
		"""Generate info line for GNTP Message

		:return string:
		"""
		info = 'GNTP/%s %s' % (
			self.info.get('version'),
			self.info.get('messagetype'),
		)
		if self.info.get('encryptionAlgorithmID', None):
			info += ' %s:%s' % (
				self.info.get('encryptionAlgorithmID'),
				self.info.get('ivValue'),
			)
		else:
			info += ' NONE'

		if self.info.get('keyHashAlgorithmID', None):
			info += ' %s:%s.%s' % (
				self.info.get('keyHashAlgorithmID'),
				self.info.get('keyHash'),
				self.info.get('salt')
			)

		return info

	def _parse_dict(self, data):
		"""Helper function to parse blocks of GNTP headers into a dictionary

		:param string data:
		:return dict: Dictionary of parsed GNTP Headers
		"""
		d = {}
		for line in data.split('\r\n'):
			match = GNTP_HEADER.match(line)
			if not match:
				continue

			key = match.group(1).strip()
			val = match.group(2).strip()
			d[key] = val
		return d

	def add_header(self, key, value):
		self.headers[key] = value

	def add_resource(self, data):
		"""Add binary resource

		:param string data: Binary Data
		"""
		data = shim.b(data)
		identifier = hashlib.md5(data).hexdigest()
		self.resources[identifier] = data
		return 'x-growl-resource://%s' % identifier

	def decode(self, data, password=None):
		"""Decode GNTP Message

		:param string data:
		"""
		self.password = password
		self.raw = shim.u(data)
		parts = self.raw.split('\r\n\r\n')
		self.info = self._parse_info(self.raw)
		self.headers = self._parse_dict(parts[0])

	def encode(self):
		"""Encode a generic GNTP Message

		:return string: GNTP Message ready to be sent. Returned as a byte string
		"""

		buff = _GNTPBuffer()

		buff.writeln(self._format_info())

		#Headers
		for k, v in self.headers.items():
			buff.writeheader(k, v)
		buff.writeln()

		#Resources
		for resource, data in self.resources.items():
			buff.writeheader('Identifier', resource)
			buff.writeheader('Length', len(data))
			buff.writeln()
			buff.write(data)
			buff.writeln()
			buff.writeln()

		return buff.getvalue()


class GNTPRegister(_GNTPBase):
	"""Represents a GNTP Registration Command

	:param string data: (Optional) See decode()
	:param string password: (Optional) Password to use while encoding/decoding messages
	"""
	_requiredHeaders = [
		'Application-Name',
		'Notifications-Count'
	]
	_requiredNotificationHeaders = ['Notification-Name']

	def __init__(self, data=None, password=None):
		_GNTPBase.__init__(self, 'REGISTER')
		self.notifications = []

		if data:
			self.decode(data, password)
		else:
			self.set_password(password)
			self.add_header('Application-Name', 'pygntp')
			self.add_header('Notifications-Count', 0)

	def validate(self):
		'''Validate required headers and validate notification headers'''
		for header in self._requiredHeaders:
			if not self.headers.get(header, False):
				raise errors.ParseError('Missing Registration Header: ' + header)
		for notice in self.notifications:
			for header in self._requiredNotificationHeaders:
				if not notice.get(header, False):
					raise errors.ParseError('Missing Notification Header: ' + header)

	def decode(self, data, password):
		"""Decode existing GNTP Registration message

		:param string data: Message to decode
		"""
		self.raw = shim.u(data)
		parts = self.raw.split('\r\n\r\n')
		self.info = self._parse_info(self.raw)
		self._validate_password(password)
		self.headers = self._parse_dict(parts[0])

		for i, part in enumerate(parts):
			if i == 0:
				continue  # Skip Header
			if part.strip() == '':
				continue
			notice = self._parse_dict(part)
			if notice.get('Notification-Name', False):
				self.notifications.append(notice)
			elif notice.get('Identifier', False):
				notice['Data'] = self._decode_binary(part, notice)
				#open('register.png','wblol').write(notice['Data'])
				self.resources[notice.get('Identifier')] = notice

	def add_notification(self, name, enabled=True):
		"""Add new Notification to Registration message

		:param string name: Notification Name
		:param boolean enabled: Enable this notification by default
		"""
		notice = {}
		notice['Notification-Name'] = name
		notice['Notification-Enabled'] = enabled

		self.notifications.append(notice)
		self.add_header('Notifications-Count', len(self.notifications))

	def encode(self):
		"""Encode a GNTP Registration Message

		:return string: Encoded GNTP Registration message. Returned as a byte string
		"""

		buff = _GNTPBuffer()

		buff.writeln(self._format_info())

		#Headers
		for k, v in self.headers.items():
			buff.writeheader(k, v)
		buff.writeln()

		#Notifications
		if len(self.notifications) > 0:
			for notice in self.notifications:
				for k, v in notice.items():
					buff.writeheader(k, v)
				buff.writeln()

		#Resources
		for resource, data in self.resources.items():
			buff.writeheader('Identifier', resource)
			buff.writeheader('Length', len(data))
			buff.writeln()
			buff.write(data)
			buff.writeln()
			buff.writeln()

		return buff.getvalue()


class GNTPNotice(_GNTPBase):
	"""Represents a GNTP Notification Command

	:param string data: (Optional) See decode()
	:param string app: (Optional) Set Application-Name
	:param string name: (Optional) Set Notification-Name
	:param string title: (Optional) Set Notification Title
	:param string password: (Optional) Password to use while encoding/decoding messages
	"""
	_requiredHeaders = [
		'Application-Name',
		'Notification-Name',
		'Notification-Title'
	]

	def __init__(self, data=None, app=None, name=None, title=None, password=None):
		_GNTPBase.__init__(self, 'NOTIFY')

		if data:
			self.decode(data, password)
		else:
			self.set_password(password)
			if app:
				self.add_header('Application-Name', app)
			if name:
				self.add_header('Notification-Name', name)
			if title:
				self.add_header('Notification-Title', title)

	def decode(self, data, password):
		"""Decode existing GNTP Notification message

		:param string data: Message to decode.
		"""
		self.raw = shim.u(data)
		parts = self.raw.split('\r\n\r\n')
		self.info = self._parse_info(self.raw)
		self._validate_password(password)
		self.headers = self._parse_dict(parts[0])

		for i, part in enumerate(parts):
			if i == 0:
				continue  # Skip Header
			if part.strip() == '':
				continue
			notice = self._parse_dict(part)
			if notice.get('Identifier', False):
				notice['Data'] = self._decode_binary(part, notice)
				#open('notice.png','wblol').write(notice['Data'])
				self.resources[notice.get('Identifier')] = notice


class GNTPSubscribe(_GNTPBase):
	"""Represents a GNTP Subscribe Command

	:param string data: (Optional) See decode()
	:param string password: (Optional) Password to use while encoding/decoding messages
	"""
	_requiredHeaders = [
		'Subscriber-ID',
		'Subscriber-Name',
	]

	def __init__(self, data=None, password=None):
		_GNTPBase.__init__(self, 'SUBSCRIBE')
		if data:
			self.decode(data, password)
		else:
			self.set_password(password)


class GNTPOK(_GNTPBase):
	"""Represents a GNTP OK Response

	:param string data: (Optional) See _GNTPResponse.decode()
	:param string action: (Optional) Set type of action the OK Response is for
	"""
	_requiredHeaders = ['Response-Action']

	def __init__(self, data=None, action=None):
		_GNTPBase.__init__(self, '-OK')
		if data:
			self.decode(data)
		if action:
			self.add_header('Response-Action', action)


class GNTPError(_GNTPBase):
	"""Represents a GNTP Error response

	:param string data: (Optional) See _GNTPResponse.decode()
	:param string errorcode: (Optional) Error code
	:param string errordesc: (Optional) Error Description
	"""
	_requiredHeaders = ['Error-Code', 'Error-Description']

	def __init__(self, data=None, errorcode=None, errordesc=None):
		_GNTPBase.__init__(self, '-ERROR')
		if data:
			self.decode(data)
		if errorcode:
			self.add_header('Error-Code', errorcode)
			self.add_header('Error-Description', errordesc)

	def error(self):
		return (self.headers.get('Error-Code', None),
			self.headers.get('Error-Description', None))


def parse_gntp(data, password=None):
	"""Attempt to parse a message as a GNTP message

	:param string data: Message to be parsed
	:param string password: Optional password to be used to verify the message
	"""
	data = shim.u(data)
	match = GNTP_INFO_LINE_SHORT.match(data)
	if not match:
		raise errors.ParseError('INVALID_GNTP_INFO')
	info = match.groupdict()
	if info['messagetype'] == 'REGISTER':
		return GNTPRegister(data, password=password)
	elif info['messagetype'] == 'NOTIFY':
		return GNTPNotice(data, password=password)
	elif info['messagetype'] == 'SUBSCRIBE':
		return GNTPSubscribe(data, password=password)
	elif info['messagetype'] == '-OK':
		return GNTPOK(data)
	elif info['messagetype'] == '-ERROR':
		return GNTPError(data)
	raise errors.ParseError('INVALID_GNTP_MESSAGE')
