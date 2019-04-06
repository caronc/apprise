# Copyright: 2013 Paul Traylor
# These sources are released under the terms of the MIT license: see LICENSE

"""
The gntp.config module is provided as an extended GrowlNotifier object that takes
advantage of the ConfigParser module to allow us to setup some default values
(such as hostname, password, and port) in a more global way to be shared among
programs using gntp
"""
import logging
import os

from .gntp import notifier
from .gntp import shim

__all__ = [
	'mini',
	'GrowlNotifier'
]

logger = logging.getLogger('gntp')


class GrowlNotifier(notifier.GrowlNotifier):
	"""
	ConfigParser enhanced GrowlNotifier object

	For right now, we are only interested in letting users overide certain
	values from ~/.gntp

	::

		[gntp]
		hostname = ?
		password = ?
		port = ?
	"""
	def __init__(self, *args, **kwargs):
		config = shim.RawConfigParser({
			'hostname': kwargs.get('hostname', 'localhost'),
			'password': kwargs.get('password'),
			'port': kwargs.get('port', 23053),
		})

		config.read([os.path.expanduser('~/.gntp')])

		# If the file does not exist, then there will be no gntp section defined
		# and the config.get() lines below will get confused. Since we are not
		# saving the config, it should be safe to just add it here so the
		# code below doesn't complain
		if not config.has_section('gntp'):
			logger.info('Error reading ~/.gntp config file')
			config.add_section('gntp')

		kwargs['password'] = config.get('gntp', 'password')
		kwargs['hostname'] = config.get('gntp', 'hostname')
		kwargs['port'] = config.getint('gntp', 'port')

		super(GrowlNotifier, self).__init__(*args, **kwargs)


def mini(description, **kwargs):
	"""Single notification function

	Simple notification function in one line. Has only one required parameter
	and attempts to use reasonable defaults for everything else
	:param string description: Notification message
	"""
	kwargs['notifierFactory'] = GrowlNotifier
	notifier.mini(description, **kwargs)


if __name__ == '__main__':
	# If we're running this module directly we're likely running it as a test
	# so extra debugging is useful
	logging.basicConfig(level=logging.INFO)
	mini('Testing mini notification')
