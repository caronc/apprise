# Copyright: 2013 Paul Traylor
# These sources are released under the terms of the MIT license: see LICENSE

import logging
import os
import sys
from optparse import OptionParser, OptionGroup

from .notifier import GrowlNotifier
from .shim import RawConfigParser
from .version import __version__

DEFAULT_CONFIG = os.path.expanduser('~/.gntp')

config = RawConfigParser({
	'hostname': 'localhost',
	'password': None,
	'port': 23053,
})
config.read([DEFAULT_CONFIG])
if not config.has_section('gntp'):
	config.add_section('gntp')


class ClientParser(OptionParser):
	def __init__(self):
		OptionParser.__init__(self, version="%%prog %s" % __version__)

		group = OptionGroup(self, "Network Options")
		group.add_option("-H", "--host",
			dest="host", default=config.get('gntp', 'hostname'),
			help="Specify a hostname to which to send a remote notification. [%default]")
		group.add_option("--port",
			dest="port", default=config.getint('gntp', 'port'), type="int",
			help="port to listen on [%default]")
		group.add_option("-P", "--password",
			dest='password', default=config.get('gntp', 'password'),
			help="Network password")
		self.add_option_group(group)

		group = OptionGroup(self, "Notification Options")
		group.add_option("-n", "--name",
			dest="app", default='Python GNTP Test Client',
			help="Set the name of the application [%default]")
		group.add_option("-s", "--sticky",
			dest='sticky', default=False, action="store_true",
			help="Make the notification sticky [%default]")
		group.add_option("--image",
			dest="icon", default=None,
			help="Icon for notification (URL or /path/to/file)")
		group.add_option("-m", "--message",
			dest="message", default=None,
			help="Sets the message instead of using stdin")
		group.add_option("-p", "--priority",
			dest="priority", default=0, type="int",
			help="-2 to 2 [%default]")
		group.add_option("-d", "--identifier",
			dest="identifier",
			help="Identifier for coalescing")
		group.add_option("-t", "--title",
			dest="title", default=None,
			help="Set the title of the notification [%default]")
		group.add_option("-N", "--notification",
			dest="name", default='Notification',
			help="Set the notification name [%default]")
		group.add_option("--callback",
			dest="callback",
			help="URL callback")
		self.add_option_group(group)

		# Extra Options
		self.add_option('-v', '--verbose',
			dest='verbose', default=0, action='count',
			help="Verbosity levels")

	def parse_args(self, args=None, values=None):
		values, args = OptionParser.parse_args(self, args, values)

		if values.message is None:
			print('Enter a message followed by Ctrl-D')
			try:
				message = sys.stdin.read()
			except KeyboardInterrupt:
				exit()
		else:
			message = values.message

		if values.title is None:
			values.title = ' '.join(args)

		# If we still have an empty title, use the
		# first bit of the message as the title
		if values.title == '':
			values.title = message[:20]

		values.verbose = logging.WARNING - values.verbose * 10

		return values, message


def main():
	(options, message) = ClientParser().parse_args()
	logging.basicConfig(level=options.verbose)
	if not os.path.exists(DEFAULT_CONFIG):
		logging.info('No config read found at %s', DEFAULT_CONFIG)

	growl = GrowlNotifier(
		applicationName=options.app,
		notifications=[options.name],
		defaultNotifications=[options.name],
		hostname=options.host,
		password=options.password,
		port=options.port,
	)
	result = growl.register()
	if result is not True:
		exit(result)

	# This would likely be better placed within the growl notifier
	# class but until I make _checkIcon smarter this is "easier"
	if options.icon is not None and not options.icon.startswith('http'):
		logging.info('Loading image %s', options.icon)
		f = open(options.icon)
		options.icon = f.read()
		f.close()

	result = growl.notify(
		noteType=options.name,
		title=options.title,
		description=message,
		icon=options.icon,
		sticky=options.sticky,
		priority=options.priority,
		callback=options.callback,
		identifier=options.identifier,
	)
	if result is not True:
		exit(result)

if __name__ == "__main__":
	main()
