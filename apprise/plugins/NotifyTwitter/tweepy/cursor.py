# Tweepy
# Copyright 2009-2010 Joshua Roesslein
# See LICENSE for details.

from __future__ import print_function

from .error import TweepError
from .parsers import ModelParser, RawParser


class Cursor(object):
    """Pagination helper class"""

    def __init__(self, method, *args, **kargs):
        if hasattr(method, 'pagination_mode'):
            if method.pagination_mode == 'cursor':
                self.iterator = CursorIterator(method, args, kargs)
            elif method.pagination_mode == 'id':
                self.iterator = IdIterator(method, args, kargs)
            elif method.pagination_mode == 'page':
                self.iterator = PageIterator(method, args, kargs)
            else:
                raise TweepError('Invalid pagination mode.')
        else:
            raise TweepError('This method does not perform pagination')

    def pages(self, limit=0):
        """Return iterator for pages"""
        if limit > 0:
            self.iterator.limit = limit
        return self.iterator

    def items(self, limit=0):
        """Return iterator for items in each page"""
        i = ItemIterator(self.iterator)
        i.limit = limit
        return i


class BaseIterator(object):

    def __init__(self, method, args, kargs):
        self.method = method
        self.args = args
        self.kargs = kargs
        self.limit = 0

    def __next__(self):
        return self.next()

    def next(self):
        raise NotImplementedError

    def prev(self):
        raise NotImplementedError

    def __iter__(self):
        return self


class CursorIterator(BaseIterator):

    def __init__(self, method, args, kargs):
        BaseIterator.__init__(self, method, args, kargs)
        start_cursor = kargs.pop('cursor', None)
        self.next_cursor = start_cursor or -1
        self.prev_cursor = start_cursor or 0
        self.num_tweets = 0

    def next(self):
        if self.next_cursor == 0 or (self.limit and self.num_tweets == self.limit):
            raise StopIteration
        data, cursors = self.method(cursor=self.next_cursor,
                                    *self.args,
                                    **self.kargs)
        self.prev_cursor, self.next_cursor = cursors
        if len(data) == 0:
            raise StopIteration
        self.num_tweets += 1
        return data

    def prev(self):
        if self.prev_cursor == 0:
            raise TweepError('Can not page back more, at first page')
        data, self.next_cursor, self.prev_cursor = self.method(cursor=self.prev_cursor,
                                                               *self.args,
                                                               **self.kargs)
        self.num_tweets -= 1
        return data


class IdIterator(BaseIterator):

    def __init__(self, method, args, kargs):
        BaseIterator.__init__(self, method, args, kargs)
        self.max_id = kargs.pop('max_id', None)
        self.num_tweets = 0
        self.results = []
        self.model_results = []
        self.index = 0

    def next(self):
        """Fetch a set of items with IDs less than current set."""
        if self.limit and self.limit == self.num_tweets:
            raise StopIteration

        if self.index >= len(self.results) - 1:
            data = self.method(max_id=self.max_id, parser=RawParser(), *self.args, **self.kargs)

            if hasattr(self.method, '__self__'):
                old_parser = self.method.__self__.parser
                # Hack for models which expect ModelParser to be set
                self.method.__self__.parser = ModelParser()

            # This is a special invocation that returns the underlying
            # APIMethod class
            model = ModelParser().parse(self.method(create=True), data)
            if hasattr(self.method, '__self__'):
                self.method.__self__.parser = old_parser
                result = self.method.__self__.parser.parse(self.method(create=True), data)
            else:
                result = model

            if len(self.results) != 0:
                self.index += 1
            self.results.append(result)
            self.model_results.append(model)
        else:
            self.index += 1
            result = self.results[self.index]
            model = self.model_results[self.index]

        if len(result) == 0:
            raise StopIteration
        # TODO: Make this not dependant on the parser making max_id and
        # since_id available
        self.max_id = model.max_id
        self.num_tweets += 1
        return result

    def prev(self):
        """Fetch a set of items with IDs greater than current set."""
        if self.limit and self.limit == self.num_tweets:
            raise StopIteration

        self.index -= 1
        if self.index < 0:
            # There's no way to fetch a set of tweets directly 'above' the
            # current set
            raise StopIteration

        data = self.results[self.index]
        self.max_id = self.model_results[self.index].max_id
        self.num_tweets += 1
        return data


class PageIterator(BaseIterator):

    def __init__(self, method, args, kargs):
        BaseIterator.__init__(self, method, args, kargs)
        self.current_page = 0

    def next(self):
        if self.limit > 0:
            if self.current_page > self.limit:
                raise StopIteration

        items = self.method(page=self.current_page, *self.args, **self.kargs)
        if len(items) == 0:
            raise StopIteration
        self.current_page += 1
        return items

    def prev(self):
        if self.current_page == 1:
            raise TweepError('Can not page back more, at first page')
        self.current_page -= 1
        return self.method(page=self.current_page, *self.args, **self.kargs)


class ItemIterator(BaseIterator):

    def __init__(self, page_iterator):
        self.page_iterator = page_iterator
        self.limit = 0
        self.current_page = None
        self.page_index = -1
        self.num_tweets = 0

    def next(self):
        if self.limit > 0:
            if self.num_tweets == self.limit:
                raise StopIteration
        if self.current_page is None or self.page_index == len(self.current_page) - 1:
            # Reached end of current page, get the next page...
            self.current_page = self.page_iterator.next()
            self.page_index = -1
        self.page_index += 1
        self.num_tweets += 1
        return self.current_page[self.page_index]

    def prev(self):
        if self.current_page is None:
            raise TweepError('Can not go back more, at first page')
        if self.page_index == 0:
            # At the beginning of the current page, move to next...
            self.current_page = self.page_iterator.prev()
            self.page_index = len(self.current_page)
            if self.page_index == 0:
                raise TweepError('No more items')
        self.page_index -= 1
        self.num_tweets -= 1
        return self.current_page[self.page_index]
