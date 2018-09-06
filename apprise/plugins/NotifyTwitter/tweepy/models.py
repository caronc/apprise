# Tweepy
# Copyright 2009-2010 Joshua Roesslein
# See LICENSE for details.

from __future__ import absolute_import, print_function

from .utils import parse_datetime, parse_html_value, parse_a_href


class ResultSet(list):
    """A list like object that holds results from a Twitter API query."""
    def __init__(self, max_id=None, since_id=None):
        super(ResultSet, self).__init__()
        self._max_id = max_id
        self._since_id = since_id

    @property
    def max_id(self):
        if self._max_id:
            return self._max_id
        ids = self.ids()
        # Max_id is always set to the *smallest* id, minus one, in the set
        return (min(ids) - 1) if ids else None

    @property
    def since_id(self):
        if self._since_id:
            return self._since_id
        ids = self.ids()
        # Since_id is always set to the *greatest* id in the set
        return max(ids) if ids else None

    def ids(self):
        return [item.id for item in self if hasattr(item, 'id')]


class Model(object):

    def __init__(self, api=None):
        self._api = api

    def __getstate__(self):
        # pickle
        pickle = dict(self.__dict__)
        try:
            del pickle['_api']  # do not pickle the API reference
        except KeyError:
            pass
        return pickle

    @classmethod
    def parse(cls, api, json):
        """Parse a JSON object into a model instance."""
        raise NotImplementedError

    @classmethod
    def parse_list(cls, api, json_list):
        """
            Parse a list of JSON objects into
            a result set of model instances.
        """
        results = ResultSet()
        for obj in json_list:
            if obj:
                results.append(cls.parse(api, obj))
        return results

    def __repr__(self):
        state = ['%s=%s' % (k, repr(v)) for (k, v) in vars(self).items()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(state))


class Status(Model):

    @classmethod
    def parse(cls, api, json):
        status = cls(api)
        setattr(status, '_json', json)
        for k, v in json.items():
            if k == 'user':
                user_model = getattr(api.parser.model_factory, 'user') if api else User
                user = user_model.parse(api, v)
                setattr(status, 'author', user)
                setattr(status, 'user', user)  # DEPRECIATED
            elif k == 'created_at':
                setattr(status, k, parse_datetime(v))
            elif k == 'source':
                if '<' in v:
                    setattr(status, k, parse_html_value(v))
                    setattr(status, 'source_url', parse_a_href(v))
                else:
                    setattr(status, k, v)
                    setattr(status, 'source_url', None)
            elif k == 'retweeted_status':
                setattr(status, k, Status.parse(api, v))
            elif k == 'quoted_status':
                setattr(status, k, Status.parse(api, v))
            elif k == 'place':
                if v is not None:
                    setattr(status, k, Place.parse(api, v))
                else:
                    setattr(status, k, None)
            else:
                setattr(status, k, v)
        return status

    def destroy(self):
        return self._api.destroy_status(self.id)

    def retweet(self):
        return self._api.retweet(self.id)

    def retweets(self):
        return self._api.retweets(self.id)

    def favorite(self):
        return self._api.create_favorite(self.id)

    def __eq__(self, other):
        if isinstance(other, Status):
            return self.id == other.id

        return NotImplemented

    def __ne__(self, other):
        result = self == other

        if result is NotImplemented:
            return result

        return not result


class User(Model):

    @classmethod
    def parse(cls, api, json):
        user = cls(api)
        setattr(user, '_json', json)
        for k, v in json.items():
            if k == 'created_at':
                setattr(user, k, parse_datetime(v))
            elif k == 'status':
                setattr(user, k, Status.parse(api, v))
            elif k == 'following':
                # twitter sets this to null if it is false
                if v is True:
                    setattr(user, k, True)
                else:
                    setattr(user, k, False)
            else:
                setattr(user, k, v)
        return user

    @classmethod
    def parse_list(cls, api, json_list):
        if isinstance(json_list, list):
            item_list = json_list
        else:
            item_list = json_list['users']

        results = ResultSet()
        for obj in item_list:
            results.append(cls.parse(api, obj))
        return results

    def timeline(self, **kargs):
        return self._api.user_timeline(user_id=self.id, **kargs)

    def friends(self, **kargs):
        return self._api.friends(user_id=self.id, **kargs)

    def followers(self, **kargs):
        return self._api.followers(user_id=self.id, **kargs)

    def follow(self):
        self._api.create_friendship(user_id=self.id)
        self.following = True

    def unfollow(self):
        self._api.destroy_friendship(user_id=self.id)
        self.following = False

    def lists_memberships(self, *args, **kargs):
        return self._api.lists_memberships(user=self.screen_name,
                                           *args,
                                           **kargs)

    def lists_subscriptions(self, *args, **kargs):
        return self._api.lists_subscriptions(user=self.screen_name,
                                             *args,
                                             **kargs)

    def lists(self, *args, **kargs):
        return self._api.lists_all(user=self.screen_name,
                                   *args,
                                   **kargs)

    def followers_ids(self, *args, **kargs):
        return self._api.followers_ids(user_id=self.id,
                                       *args,
                                       **kargs)


class DirectMessage(Model):

    @classmethod
    def parse(cls, api, json):
        dm = cls(api)
        for k, v in json.items():
            if k == 'sender' or k == 'recipient':
                setattr(dm, k, User.parse(api, v))
            elif k == 'created_at':
                setattr(dm, k, parse_datetime(v))
            else:
                setattr(dm, k, v)
        return dm

    def destroy(self):
        return self._api.destroy_direct_message(self.id)


class Friendship(Model):

    @classmethod
    def parse(cls, api, json):
        relationship = json['relationship']

        # parse source
        source = cls(api)
        for k, v in relationship['source'].items():
            setattr(source, k, v)

        # parse target
        target = cls(api)
        for k, v in relationship['target'].items():
            setattr(target, k, v)

        return source, target


class Category(Model):

    @classmethod
    def parse(cls, api, json):
        category = cls(api)
        for k, v in json.items():
            setattr(category, k, v)
        return category


class SavedSearch(Model):

    @classmethod
    def parse(cls, api, json):
        ss = cls(api)
        for k, v in json.items():
            if k == 'created_at':
                setattr(ss, k, parse_datetime(v))
            else:
                setattr(ss, k, v)
        return ss

    def destroy(self):
        return self._api.destroy_saved_search(self.id)


class SearchResults(ResultSet):

    @classmethod
    def parse(cls, api, json):
        metadata = json['search_metadata']
        results = SearchResults()
        results.refresh_url = metadata.get('refresh_url')
        results.completed_in = metadata.get('completed_in')
        results.query = metadata.get('query')
        results.count = metadata.get('count')
        results.next_results = metadata.get('next_results')

        status_model = getattr(api.parser.model_factory, 'status') if api else Status

        for status in json['statuses']:
            results.append(status_model.parse(api, status))
        return results


class List(Model):

    @classmethod
    def parse(cls, api, json):
        lst = List(api)
        for k, v in json.items():
            if k == 'user':
                setattr(lst, k, User.parse(api, v))
            elif k == 'created_at':
                setattr(lst, k, parse_datetime(v))
            else:
                setattr(lst, k, v)
        return lst

    @classmethod
    def parse_list(cls, api, json_list, result_set=None):
        results = ResultSet()
        if isinstance(json_list, dict):
            json_list = json_list['lists']
        for obj in json_list:
            results.append(cls.parse(api, obj))
        return results

    def update(self, **kargs):
        return self._api.update_list(self.slug, **kargs)

    def destroy(self):
        return self._api.destroy_list(self.slug)

    def timeline(self, **kargs):
        return self._api.list_timeline(self.user.screen_name,
                                       self.slug,
                                       **kargs)

    def add_member(self, id):
        return self._api.add_list_member(self.slug, id)

    def remove_member(self, id):
        return self._api.remove_list_member(self.slug, id)

    def members(self, **kargs):
        return self._api.list_members(self.user.screen_name,
                                      self.slug,
                                      **kargs)

    def is_member(self, id):
        return self._api.is_list_member(self.user.screen_name,
                                        self.slug,
                                        id)

    def subscribe(self):
        return self._api.subscribe_list(self.user.screen_name, self.slug)

    def unsubscribe(self):
        return self._api.unsubscribe_list(self.user.screen_name, self.slug)

    def subscribers(self, **kargs):
        return self._api.list_subscribers(self.user.screen_name,
                                          self.slug,
                                          **kargs)

    def is_subscribed(self, id):
        return self._api.is_subscribed_list(self.user.screen_name,
                                            self.slug,
                                            id)


class Relation(Model):
    @classmethod
    def parse(cls, api, json):
        result = cls(api)
        for k, v in json.items():
            if k == 'value' and json['kind'] in ['Tweet', 'LookedupStatus']:
                setattr(result, k, Status.parse(api, v))
            elif k == 'results':
                setattr(result, k, Relation.parse_list(api, v))
            else:
                setattr(result, k, v)
        return result


class Relationship(Model):
    @classmethod
    def parse(cls, api, json):
        result = cls(api)
        for k, v in json.items():
            if k == 'connections':
                setattr(result, 'is_following', 'following' in v)
                setattr(result, 'is_followed_by', 'followed_by' in v)
            else:
                setattr(result, k, v)
        return result


class JSONModel(Model):

    @classmethod
    def parse(cls, api, json):
        return json


class IDModel(Model):

    @classmethod
    def parse(cls, api, json):
        if isinstance(json, list):
            return json
        else:
            return json['ids']


class BoundingBox(Model):

    @classmethod
    def parse(cls, api, json):
        result = cls(api)
        if json is not None:
            for k, v in json.items():
                setattr(result, k, v)
        return result

    def origin(self):
        """
        Return longitude, latitude of southwest (bottom, left) corner of
        bounding box, as a tuple.

        This assumes that bounding box is always a rectangle, which
        appears to be the case at present.
        """
        return tuple(self.coordinates[0][0])

    def corner(self):
        """
        Return longitude, latitude of northeast (top, right) corner of
        bounding box, as a tuple.

        This assumes that bounding box is always a rectangle, which
        appears to be the case at present.
        """
        return tuple(self.coordinates[0][2])


class Place(Model):

    @classmethod
    def parse(cls, api, json):
        place = cls(api)
        for k, v in json.items():
            if k == 'bounding_box':
                # bounding_box value may be null (None.)
                # Example: "United States" (id=96683cc9126741d1)
                if v is not None:
                    t = BoundingBox.parse(api, v)
                else:
                    t = v
                setattr(place, k, t)
            elif k == 'contained_within':
                # contained_within is a list of Places.
                setattr(place, k, Place.parse_list(api, v))
            else:
                setattr(place, k, v)
        return place

    @classmethod
    def parse_list(cls, api, json_list):
        if isinstance(json_list, list):
            item_list = json_list
        else:
            item_list = json_list['result']['places']

        results = ResultSet()
        for obj in item_list:
            results.append(cls.parse(api, obj))
        return results


class Media(Model):

    @classmethod
    def parse(cls, api, json):
        media = cls(api)
        for k, v in json.items():
            setattr(media, k, v)
        return media


class ModelFactory(object):
    """
    Used by parsers for creating instances
    of models. You may subclass this factory
    to add your own extended models.
    """

    status = Status
    user = User
    direct_message = DirectMessage
    friendship = Friendship
    saved_search = SavedSearch
    search_results = SearchResults
    category = Category
    list = List
    relation = Relation
    relationship = Relationship
    media = Media

    json = JSONModel
    ids = IDModel
    place = Place
    bounding_box = BoundingBox
