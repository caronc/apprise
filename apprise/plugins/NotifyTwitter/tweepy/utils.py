# Tweepy
# Copyright 2010 Joshua Roesslein
# See LICENSE for details.

from __future__ import print_function

from datetime import datetime

import six
from six.moves.urllib.parse import quote

from email.utils import parsedate


def parse_datetime(string):
    return datetime(*(parsedate(string)[:6]))


def parse_html_value(html):

    return html[html.find('>')+1:html.rfind('<')]


def parse_a_href(atag):

    start = atag.find('"') + 1
    end = atag.find('"', start)
    return atag[start:end]


def convert_to_utf8_str(arg):
    # written by Michael Norton (http://docondev.blogspot.com/)
    if isinstance(arg, six.text_type):
        arg = arg.encode('utf-8')
    elif not isinstance(arg, bytes):
        arg = six.text_type(arg).encode('utf-8')
    return arg


def import_simplejson():
    try:
        import simplejson as json
    except ImportError:
        try:
            import json  # Python 2.6+
        except ImportError:
            try:
                # Google App Engine
                from django.utils import simplejson as json
            except ImportError:
                raise ImportError("Can't load a json library")

    return json


def list_to_csv(item_list):
    if item_list:
        return ','.join([str(i) for i in item_list])
