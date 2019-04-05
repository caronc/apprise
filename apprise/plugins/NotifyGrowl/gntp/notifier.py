# Copyright: 2013 Paul Traylor
# These sources are released under the terms of the MIT license: see LICENSE

"""
The gntp.notifier module is provided as a simple way to send notifications
using GNTP

.. note::
	This class is intended to mostly mirror the older Python bindings such
	that you should be able to replace instances of the old bindings with
	this class.
	`Original Python bindings <http://code.google.com/p/growl/source/browse/Bindings/python/Growl.py>`_

"""
import logging
import platform
import socket
import sys

from .version import __version__
from . import core
from . import errors as errors
from . import shim

__all__ = [
	'mini',
	'GrowlNotifier',
]

logger = logging.getLogger('gntp')


class GrowlNotifier(object):
	"""Helper class to simplfy sending Growl messages

	:param string applicationName: Sending application name
	:param list notification: List of valid notifications
	:param list defaultNotifications: List of notifications that should be enabled
		by default
	:param string applicationIcon: Icon URL
	:param string hostname: Remote host
	:param integer port: Remote port
	"""

	passwordHash = 'MD5'
	socketTimeout = 3

	def __init__(self, applicationName='Python GNTP', notifications=[],
			defaultNotifications=None, applicationIcon=None, hostname='localhost',
			password=None, port=23053):

		self.applicationName = applicationName
		self.notifications = list(notifications)
		if defaultNotifications:
			self.defaultNotifications = list(defaultNotifications)
		else:
			self.defaultNotifications = self.notifications
		self.applicationIcon = applicationIcon

		self.password = password
		self.hostname = hostname
		self.port = int(port)

	def _checkIcon(self, data):
		'''
		Check the icon to see if it's valid

		If it's a simple URL icon, then we return True. If it's a data icon
		then we return False
		'''
		logger.info('Checking icon')
		return shim.u(data).startswith('http')

	def register(self):
		"""Send GNTP Registration

		.. warning::
			Before sending notifications to Growl, you need to have
			sent a registration message at least once
		"""
		logger.info('Sending registration to %s:%s', self.hostname, self.port)
		register = core.GNTPRegister()
		register.add_header('Application-Name', self.applicationName)
		for notification in self.notifications:
			enabled = notification in self.defaultNotifications
			register.add_notification(notification, enabled)
		if self.applicationIcon:
			if self._checkIcon(self.applicationIcon):
				register.add_header('Application-Icon', self.applicationIcon)
			else:
				resource = register.add_resource(self.applicationIcon)
				register.add_header('Application-Icon', resource)
		if self.password:
			register.set_password(self.password, self.passwordHash)
		self.add_origin_info(register)
		self.register_hook(register)
		return self._send('register', register)

	def notify(self, noteType, title, description, icon=None, sticky=False,
			priority=None, callback=None, identifier=None, custom={}):
		"""Send a GNTP notifications

		.. warning::
			Must have registered with growl beforehand or messages will be ignored

		:param string noteType: One of the notification names registered earlier
		:param string title: Notification title (usually displayed on the notification)
		:param string description: The main content of the notification
		:param string icon: Icon URL path
		:param boolean sticky: Sticky notification
		:param integer priority: Message priority level from -2 to 2
		:param string callback:  URL callback
		:param dict custom: Custom attributes. Key names should be prefixed with X-
			according to the spec but this is not enforced by this class

		.. warning::
			For now, only URL callbacks are supported. In the future, the
			callback argument will also support a function
		"""
		logger.info('Sending notification [%s] to %s:%s', noteType, self.hostname, self.port)
		assert noteType in self.notifications
		notice = core.GNTPNotice()
		notice.add_header('Application-Name', self.applicationName)
		notice.add_header('Notification-Name', noteType)
		notice.add_header('Notification-Title', title)
		if self.password:
			notice.set_password(self.password, self.passwordHash)
		if sticky:
			notice.add_header('Notification-Sticky', sticky)
		if priority:
			notice.add_header('Notification-Priority', priority)
		if icon:
			if self._checkIcon(icon):
				notice.add_header('Notification-Icon', icon)
			else:
				resource = notice.add_resource(icon)
				notice.add_header('Notification-Icon', resource)

		if description:
			notice.add_header('Notification-Text', description)
		if callback:
			notice.add_header('Notification-Callback-Target', callback)
		if identifier:
			notice.add_header('Notification-Coalescing-ID', identifier)

		for key in custom:
			notice.add_header(key, custom[key])

		self.add_origin_info(notice)
		self.notify_hook(notice)

		return self._send('notify', notice)

	def subscribe(self, id, name, port):
		"""Send a Subscribe request to a remote machine"""
		sub = core.GNTPSubscribe()
		sub.add_header('Subscriber-ID', id)
		sub.add_header('Subscriber-Name', name)
		sub.add_header('Subscriber-Port', port)
		if self.password:
			sub.set_password(self.password, self.passwordHash)

		self.add_origin_info(sub)
		self.subscribe_hook(sub)

		return self._send('subscribe', sub)

	def add_origin_info(self, packet):
		"""Add optional Origin headers to message"""
		packet.add_header('Origin-Machine-Name', platform.node())
		packet.add_header('Origin-Software-Name', 'gntp.py')
		packet.add_header('Origin-Software-Version', __version__)
		packet.add_header('Origin-Platform-Name', platform.system())
		packet.add_header('Origin-Platform-Version', platform.platform())

	def register_hook(self, packet):
		pass

	def notify_hook(self, packet):
		pass

	def subscribe_hook(self, packet):
		pass

	def _send(self, messagetype, packet):
		"""Send the GNTP Packet"""

		packet.validate()
		data = packet.encode()

		logger.debug('To : %s:%s <%s>\n%s', self.hostname, self.port, packet.__class__, data)

		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.settimeout(self.socketTimeout)
		try:
			s.connect((self.hostname, self.port))
			s.send(data)
			recv_data = s.recv(1024)
			while not recv_data.endswith(shim.b("\r\n\r\n")):
				recv_data += s.recv(1024)
		except socket.error:
			# Python2.5 and Python3 compatibile exception
			exc = sys.exc_info()[1]
			raise errors.NetworkError(exc)

		response = core.parse_gntp(recv_data)
		s.close()

		logger.debug('From : %s:%s <%s>\n%s', self.hostname, self.port, response.__class__, response)

		if type(response) == core.GNTPOK:
			return True
		logger.error('Invalid response: %s', response.error())
		return response.error()


def mini(description, applicationName='PythonMini', noteType="Message",
			title="Mini Message", applicationIcon=None, hostname='localhost',
			password=None, port=23053, sticky=False, priority=None,
			callback=None, notificationIcon=None, identifier=None,
			notifierFactory=GrowlNotifier):
	"""Single notification function

	Simple notification function in one line. Has only one required parameter
	and attempts to use reasonable defaults for everything else
	:param string description: Notification message

	.. warning::
			For now, only URL callbacks are supported. In the future, the
			callback argument will also support a function
	"""
	try:
		growl = notifierFactory(
			applicationName=applicationName,
			notifications=[noteType],
			defaultNotifications=[noteType],
			applicationIcon=applicationIcon,
			hostname=hostname,
			password=password,
			port=port,
		)
		result = growl.register()
		if result is not True:
			return result

		return growl.notify(
			noteType=noteType,
			title=title,
			description=description,
			icon=notificationIcon,
			sticky=sticky,
			priority=priority,
			callback=callback,
			identifier=identifier,
		)
	except Exception:
		# We want the "mini" function to be simple and swallow Exceptions
		# in order to be less invasive
		logger.exception("Growl error")

if __name__ == '__main__':
	# If we're running this module directly we're likely running it as a test
	# so extra debugging is useful
	logging.basicConfig(level=logging.INFO)
	mini('Testing mini notification')
