# Tweepy
# Copyright 2009-2010 Joshua Roesslein
# See LICENSE for details.

from __future__ import print_function

import os
import mimetypes

import six

from .binder import bind_api
from .error import TweepError
from .parsers import ModelParser, Parser
from .utils import list_to_csv


class API(object):
    """Twitter API"""

    def __init__(self, auth_handler=None,
                 host='api.twitter.com', search_host='search.twitter.com',
                 upload_host='upload.twitter.com', cache=None, api_root='/1.1',
                 search_root='', upload_root='/1.1', retry_count=0,
                 retry_delay=0, retry_errors=None, timeout=60, parser=None,
                 compression=False, wait_on_rate_limit=False,
                 wait_on_rate_limit_notify=False, proxy=''):
        """ Api instance Constructor

        :param auth_handler:
        :param host:  url of the server of the rest api, default:'api.twitter.com'
        :param search_host: url of the search server, default:'search.twitter.com'
        :param upload_host: url of the upload server, default:'upload.twitter.com'
        :param cache: Cache to query if a GET method is used, default:None
        :param api_root: suffix of the api version, default:'/1.1'
        :param search_root: suffix of the search version, default:''
        :param upload_root: suffix of the upload version, default:'/1.1'
        :param retry_count: number of allowed retries, default:0
        :param retry_delay: delay in second between retries, default:0
        :param retry_errors: default:None
        :param timeout: delay before to consider the request as timed out in seconds, default:60
        :param parser: ModelParser instance to parse the responses, default:None
        :param compression: If the response is compressed, default:False
        :param wait_on_rate_limit: If the api wait when it hits the rate limit, default:False
        :param wait_on_rate_limit_notify: If the api print a notification when the rate limit is hit, default:False
        :param proxy: Url to use as proxy during the HTTP request, default:''

        :raise TypeError: If the given parser is not a ModelParser instance.
        """
        self.auth = auth_handler
        self.host = host
        self.search_host = search_host
        self.upload_host = upload_host
        self.api_root = api_root
        self.search_root = search_root
        self.upload_root = upload_root
        self.cache = cache
        self.compression = compression
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.retry_errors = retry_errors
        self.timeout = timeout
        self.wait_on_rate_limit = wait_on_rate_limit
        self.wait_on_rate_limit_notify = wait_on_rate_limit_notify
        self.parser = parser or ModelParser()
        self.proxy = {}
        if proxy:
            self.proxy['https'] = proxy

        # Attempt to explain more clearly the parser argument requirements
        # https://github.com/tweepy/tweepy/issues/421
        #
        parser_type = Parser
        if not isinstance(self.parser, parser_type):
            raise TypeError(
                '"parser" argument has to be an instance of "{required}".'
                ' It is currently a {actual}.'.format(
                    required=parser_type.__name__,
                    actual=type(self.parser)
                )
            )

    @property
    def home_timeline(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/home_timeline
            :allowed_param:'since_id', 'max_id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/home_timeline.json',
            payload_type='status', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count'],
            require_auth=True
        )

    def statuses_lookup(self, id_, include_entities=None,
                        trim_user=None, map_=None, tweet_mode=None):
        return self._statuses_lookup(list_to_csv(id_), include_entities,
                                     trim_user, map_, tweet_mode)

    @property
    def _statuses_lookup(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/lookup
            :allowed_param:'id', 'include_entities', 'trim_user', 'map', 'tweet_mode'
        """
        return bind_api(
            api=self,
            path='/statuses/lookup.json',
            payload_type='status', payload_list=True,
            allowed_param=['id', 'include_entities', 'trim_user', 'map', 'tweet_mode'],
            require_auth=True
        )

    @property
    def user_timeline(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/user_timeline
            :allowed_param:'id', 'user_id', 'screen_name', 'since_id', 'max_id', 'count', 'include_rts', 'trim_user', 'exclude_replies'
        """
        return bind_api(
            api=self,
            path='/statuses/user_timeline.json',
            payload_type='status', payload_list=True,
            allowed_param=['id', 'user_id', 'screen_name', 'since_id',
                           'max_id', 'count', 'include_rts', 'trim_user',
                           'exclude_replies']
        )

    @property
    def mentions_timeline(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/mentions_timeline
            :allowed_param:'since_id', 'max_id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/mentions_timeline.json',
            payload_type='status', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count'],
            require_auth=True
        )

    @property
    def related_results(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/related_results/show/%3id.format
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/related_results/show/{id}.json',
            payload_type='relation', payload_list=True,
            allowed_param=['id'],
            require_auth=False
        )

    @property
    def retweets_of_me(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/retweets_of_me
            :allowed_param:'since_id', 'max_id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/retweets_of_me.json',
            payload_type='status', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count'],
            require_auth=True
        )

    @property
    def get_status(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/show/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/statuses/show.json',
            payload_type='status',
            allowed_param=['id']
        )

    def update_status(self, *args, **kwargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/update
            :allowed_param:'status', 'in_reply_to_status_id', 'in_reply_to_status_id_str', 'auto_populate_reply_metadata', 'lat', 'long', 'source', 'place_id', 'display_coordinates', 'media_ids'
        """
        post_data = {}
        media_ids = kwargs.pop("media_ids", None)
        if media_ids is not None:
            post_data["media_ids"] = list_to_csv(media_ids)

        return bind_api(
            api=self,
            path='/statuses/update.json',
            method='POST',
            payload_type='status',
            allowed_param=['status', 'in_reply_to_status_id', 'in_reply_to_status_id_str', 'auto_populate_reply_metadata', 'lat', 'long', 'source', 'place_id', 'display_coordinates'],
            require_auth=True
        )(post_data=post_data, *args, **kwargs)

    def media_upload(self, filename, *args, **kwargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/media/upload
            :allowed_param:
        """
        f = kwargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 4883, form_field='media', f=f)
        kwargs.update({'headers': headers, 'post_data': post_data})

        return bind_api(
            api=self,
            path='/media/upload.json',
            method='POST',
            payload_type='media',
            allowed_param=[],
            require_auth=True,
            upload_api=True
        )(*args, **kwargs)

    def update_with_media(self, filename, *args, **kwargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/update_with_media
            :allowed_param:'status', 'possibly_sensitive', 'in_reply_to_status_id', 'in_reply_to_status_id_str', 'auto_populate_reply_metadata', 'lat', 'long', 'place_id', 'display_coordinates'
        """
        f = kwargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 3072, form_field='media[]', f=f)
        kwargs.update({'headers': headers, 'post_data': post_data})

        return bind_api(
            api=self,
            path='/statuses/update_with_media.json',
            method='POST',
            payload_type='status',
            allowed_param=[
                'status', 'possibly_sensitive', 'in_reply_to_status_id', 'in_reply_to_status_id_str',
                'auto_populate_reply_metadata', 'lat', 'long', 'place_id', 'display_coordinates'
            ],
            require_auth=True
        )(*args, **kwargs)

    @property
    def destroy_status(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/destroy/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/statuses/destroy/{id}.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def retweet(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/retweet/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/statuses/retweet/{id}.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def unretweet(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/statuses/unretweet/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/statuses/unretweet/{id}.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def retweets(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/retweets/%3Aid
            :allowed_param:'id', 'count'
        """
        return bind_api(
            api=self,
            path='/statuses/retweets/{id}.json',
            payload_type='status', payload_list=True,
            allowed_param=['id', 'count'],
            require_auth=True
        )

    @property
    def retweeters(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/retweeters/ids
            :allowed_param:'id', 'cursor', 'stringify_ids
        """
        return bind_api(
            api=self,
            path='/statuses/retweeters/ids.json',
            payload_type='ids',
            allowed_param=['id', 'cursor', 'stringify_ids']
        )

    @property
    def get_user(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/show
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/users/show.json',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name']
        )

    @property
    def get_oembed(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/statuses/oembed
            :allowed_param:'id', 'url', 'maxwidth', 'hide_media', 'omit_script', 'align', 'related', 'lang'
        """
        return bind_api(
            api=self,
            path='/statuses/oembed.json',
            payload_type='json',
            allowed_param=['id', 'url', 'maxwidth', 'hide_media', 'omit_script', 'align', 'related', 'lang']
        )

    def lookup_users(self, user_ids=None, screen_names=None, include_entities=None):
        """ Perform bulk look up of users from user ID or screenname """
        post_data = {}
        if include_entities is not None:
            include_entities = 'true' if include_entities else 'false'
            post_data['include_entities'] = include_entities
        if user_ids:
            post_data['user_id'] = list_to_csv(user_ids)
        if screen_names:
            post_data['screen_name'] = list_to_csv(screen_names)

        return self._lookup_users(post_data=post_data)

    @property
    def _lookup_users(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/lookup
            allowed_param='user_id', 'screen_name', 'include_entities'
        """
        return bind_api(
            api=self,
            path='/users/lookup.json',
            payload_type='user', payload_list=True,
            method='POST',
            allowed_param=['user_id', 'screen_name', 'include_entities']
        )

    def me(self):
        """ Get the authenticated user """
        return self.get_user(screen_name=self.auth.get_username())

    @property
    def search_users(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/search
            :allowed_param:'q', 'count', 'page'
        """
        return bind_api(
            api=self,
            path='/users/search.json',
            payload_type='user', payload_list=True,
            require_auth=True,
            allowed_param=['q', 'count', 'page']
        )

    @property
    def suggested_users(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/suggestions/%3Aslug
            :allowed_param:'slug', 'lang'
        """
        return bind_api(
            api=self,
            path='/users/suggestions/{slug}.json',
            payload_type='user', payload_list=True,
            require_auth=True,
            allowed_param=['slug', 'lang']
        )

    @property
    def suggested_categories(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/suggestions
            :allowed_param:'lang'
        """
        return bind_api(
            api=self,
            path='/users/suggestions.json',
            payload_type='category', payload_list=True,
            allowed_param=['lang'],
            require_auth=True
        )

    @property
    def suggested_users_tweets(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/users/suggestions/%3Aslug/members
            :allowed_param:'slug'
        """
        return bind_api(
            api=self,
            path='/users/suggestions/{slug}/members.json',
            payload_type='status', payload_list=True,
            allowed_param=['slug'],
            require_auth=True
        )

    @property
    def direct_messages(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/direct_messages
            :allowed_param:'since_id', 'max_id', 'count', 'full_text'
        """
        return bind_api(
            api=self,
            path='/direct_messages.json',
            payload_type='direct_message', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count', 'full_text'],
            require_auth=True
        )

    @property
    def get_direct_message(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/direct_messages/show
            :allowed_param:'id', 'full_text'
        """
        return bind_api(
            api=self,
            path='/direct_messages/show/{id}.json',
            payload_type='direct_message',
            allowed_param=['id', 'full_text'],
            require_auth=True
        )

    @property
    def sent_direct_messages(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/direct_messages/sent
            :allowed_param:'since_id', 'max_id', 'count', 'page', 'full_text'
        """
        return bind_api(
            api=self,
            path='/direct_messages/sent.json',
            payload_type='direct_message', payload_list=True,
            allowed_param=['since_id', 'max_id', 'count', 'page', 'full_text'],
            require_auth=True
        )

    @property
    def send_direct_message(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/direct_messages/new
            :allowed_param:'user', 'screen_name', 'user_id', 'text'
        """
        return bind_api(
            api=self,
            path='/direct_messages/new.json',
            method='POST',
            payload_type='direct_message',
            allowed_param=['user', 'screen_name', 'user_id', 'text'],
            require_auth=True
        )

    @property
    def destroy_direct_message(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/direct_messages/destroy
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/direct_messages/destroy.json',
            method='POST',
            payload_type='direct_message',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_friendship(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/friendships/create
            :allowed_param:'id', 'user_id', 'screen_name', 'follow'
        """
        return bind_api(
            api=self,
            path='/friendships/create.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name', 'follow'],
            require_auth=True
        )

    @property
    def destroy_friendship(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/friendships/destroy
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/friendships/destroy.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def show_friendship(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/show
            :allowed_param:'source_id', 'source_screen_name', 'target_id', 'target_screen_name'
        """
        return bind_api(
            api=self,
            path='/friendships/show.json',
            payload_type='friendship',
            allowed_param=['source_id', 'source_screen_name',
                           'target_id', 'target_screen_name']
        )

    def lookup_friendships(self, user_ids=None, screen_names=None):
        """ Perform bulk look up of friendships from user ID or screenname """
        return self._lookup_friendships(list_to_csv(user_ids), list_to_csv(screen_names))

    @property
    def _lookup_friendships(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/lookup
            :allowed_param:'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/friendships/lookup.json',
            payload_type='relationship', payload_list=True,
            allowed_param=['user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def friends_ids(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friends/ids
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor'
        """
        return bind_api(
            api=self,
            path='/friends/ids.json',
            payload_type='ids',
            allowed_param=['id', 'user_id', 'screen_name', 'cursor']
        )

    @property
    def friends(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friends/list
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor', 'skip_status', 'include_user_entities'
        """
        return bind_api(
            api=self,
            path='/friends/list.json',
            payload_type='user', payload_list=True,
            allowed_param=['id', 'user_id', 'screen_name', 'cursor', 'skip_status', 'include_user_entities']
        )

    @property
    def friendships_incoming(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/incoming
            :allowed_param:'cursor'
        """
        return bind_api(
            api=self,
            path='/friendships/incoming.json',
            payload_type='ids',
            allowed_param=['cursor']
        )

    @property
    def friendships_outgoing(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/friendships/outgoing
            :allowed_param:'cursor'
        """
        return bind_api(
            api=self,
            path='/friendships/outgoing.json',
            payload_type='ids',
            allowed_param=['cursor']
        )

    @property
    def followers_ids(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/followers/ids
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor', 'count'
        """
        return bind_api(
            api=self,
            path='/followers/ids.json',
            payload_type='ids',
            allowed_param=['id', 'user_id', 'screen_name', 'cursor', 'count']
        )

    @property
    def followers(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/followers/list
            :allowed_param:'id', 'user_id', 'screen_name', 'cursor', 'count', 'skip_status', 'include_user_entities'
        """
        return bind_api(
            api=self,
            path='/followers/list.json',
            payload_type='user', payload_list=True,
            allowed_param=['id', 'user_id', 'screen_name', 'cursor', 'count',
                           'skip_status', 'include_user_entities']
        )

    @property
    def get_settings(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/account/settings
        """
        return bind_api(
            api=self,
            path='/account/settings.json',
            payload_type='json',
            use_cache=False
        )

    @property
    def set_settings(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/settings
            :allowed_param:'sleep_time_enabled', 'start_sleep_time',
            'end_sleep_time', 'time_zone', 'trend_location_woeid',
            'allow_contributor_request', 'lang'
        """
        return bind_api(
            api=self,
            path='/account/settings.json',
            method='POST',
            payload_type='json',
            allowed_param=['sleep_time_enabled', 'start_sleep_time',
                           'end_sleep_time', 'time_zone',
                           'trend_location_woeid', 'allow_contributor_request',
                           'lang'],
            use_cache=False
        )

    def verify_credentials(self, **kargs):
        """ :reference: https://dev.twitter.com/rest/reference/get/account/verify_credentials
            :allowed_param:'include_entities', 'skip_status', 'include_email'
        """
        try:
            return bind_api(
                api=self,
                path='/account/verify_credentials.json',
                payload_type='user',
                require_auth=True,
                allowed_param=['include_entities', 'skip_status', 'include_email'],
            )(**kargs)
        except TweepError as e:
            if e.response and e.response.status == 401:
                return False
            raise

    @property
    def rate_limit_status(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/application/rate_limit_status
            :allowed_param:'resources'
        """
        return bind_api(
            api=self,
            path='/application/rate_limit_status.json',
            payload_type='json',
            allowed_param=['resources'],
            use_cache=False
        )

    @property
    def set_delivery_device(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_delivery_device
            :allowed_param:'device'
        """
        return bind_api(
            api=self,
            path='/account/update_delivery_device.json',
            method='POST',
            allowed_param=['device'],
            payload_type='user',
            require_auth=True
        )

    def update_profile_image(self, filename, file_=None):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile_image
            :allowed_param:'include_entities', 'skip_status'
        """
        headers, post_data = API._pack_image(filename, 700, f=file_)
        return bind_api(
            api=self,
            path='/account/update_profile_image.json',
            method='POST',
            payload_type='user',
            allowed_param=['include_entities', 'skip_status'],
            require_auth=True
        )(self, post_data=post_data, headers=headers)

    def update_profile_background_image(self, filename, **kargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile_background_image
            :allowed_param:'tile', 'include_entities', 'skip_status', 'use'
        """
        f = kargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 800, f=f)
        bind_api(
            api=self,
            path='/account/update_profile_background_image.json',
            method='POST',
            payload_type='user',
            allowed_param=['tile', 'include_entities', 'skip_status', 'use'],
            require_auth=True
        )(post_data=post_data, headers=headers)

    def update_profile_banner(self, filename, **kargs):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile_banner
            :allowed_param:'width', 'height', 'offset_left', 'offset_right'
        """
        f = kargs.pop('file', None)
        headers, post_data = API._pack_image(filename, 700, form_field="banner", f=f)
        bind_api(
            api=self,
            path='/account/update_profile_banner.json',
            method='POST',
            allowed_param=['width', 'height', 'offset_left', 'offset_right'],
            require_auth=True
        )(post_data=post_data, headers=headers)

    @property
    def update_profile(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/account/update_profile
            :allowed_param:'name', 'url', 'location', 'description', 'profile_link_color'
        """
        return bind_api(
            api=self,
            path='/account/update_profile.json',
            method='POST',
            payload_type='user',
            allowed_param=['name', 'url', 'location', 'description', 'profile_link_color'],
            require_auth=True
        )

    @property
    def favorites(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/favorites/list
            :allowed_param:'screen_name', 'user_id', 'max_id', 'count', 'since_id', 'max_id'
        """
        return bind_api(
            api=self,
            path='/favorites/list.json',
            payload_type='status', payload_list=True,
            allowed_param=['screen_name', 'user_id', 'max_id', 'count', 'since_id', 'max_id']
        )

    @property
    def create_favorite(self):
        """ :reference:https://dev.twitter.com/rest/reference/post/favorites/create
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/favorites/create.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def destroy_favorite(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/favorites/destroy
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/favorites/destroy.json',
            method='POST',
            payload_type='status',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_block(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/blocks/create
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/blocks/create.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def destroy_block(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/blocks/destroy
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/blocks/destroy.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def mutes_ids(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/mutes/users/ids """
        return bind_api(
            api=self,
            path='/mutes/users/ids.json',
            payload_type='json',
            require_auth=True
        )

    @property
    def create_mute(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/mutes/users/create
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/mutes/users/create.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def destroy_mute(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/mutes/users/destroy
            :allowed_param:'id', 'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/mutes/users/destroy.json',
            method='POST',
            payload_type='user',
            allowed_param=['id', 'user_id', 'screen_name'],
            require_auth=True
        )



    @property
    def blocks(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/blocks/list
            :allowed_param:'cursor'
        """
        return bind_api(
            api=self,
            path='/blocks/list.json',
            payload_type='user', payload_list=True,
            allowed_param=['cursor'],
            require_auth=True
        )

    @property
    def blocks_ids(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/blocks/ids """
        return bind_api(
            api=self,
            path='/blocks/ids.json',
            payload_type='json',
            require_auth=True
        )

    @property
    def report_spam(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/users/report_spam
            :allowed_param:'user_id', 'screen_name'
        """
        return bind_api(
            api=self,
            path='/users/report_spam.json',
            method='POST',
            payload_type='user',
            allowed_param=['user_id', 'screen_name'],
            require_auth=True
        )

    @property
    def saved_searches(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/saved_searches/show/%3Aid """
        return bind_api(
            api=self,
            path='/saved_searches/list.json',
            payload_type='saved_search', payload_list=True,
            require_auth=True
        )

    @property
    def get_saved_search(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/saved_searches/show/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/saved_searches/show/{id}.json',
            payload_type='saved_search',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_saved_search(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/saved_searches/create
            :allowed_param:'query'
        """
        return bind_api(
            api=self,
            path='/saved_searches/create.json',
            method='POST',
            payload_type='saved_search',
            allowed_param=['query'],
            require_auth=True
        )

    @property
    def destroy_saved_search(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/saved_searches/destroy/%3Aid
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/saved_searches/destroy/{id}.json',
            method='POST',
            payload_type='saved_search',
            allowed_param=['id'],
            require_auth=True
        )

    @property
    def create_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/lists/create
            :allowed_param:'name', 'mode', 'description'
        """
        return bind_api(
            api=self,
            path='/lists/create.json',
            method='POST',
            payload_type='list',
            allowed_param=['name', 'mode', 'description'],
            require_auth=True
        )

    @property
    def destroy_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/lists/destroy
            :allowed_param:'owner_screen_name', 'owner_id', 'list_id', 'slug'
        """
        return bind_api(
            api=self,
            path='/lists/destroy.json',
            method='POST',
            payload_type='list',
            allowed_param=['owner_screen_name', 'owner_id', 'list_id', 'slug'],
            require_auth=True
        )

    @property
    def update_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/post/lists/update
            :allowed_param: list_id', 'slug', 'name', 'mode', 'description', 'owner_screen_name', 'owner_id'
        """
        return bind_api(
            api=self,
            path='/lists/update.json',
            method='POST',
            payload_type='list',
            allowed_param=['list_id', 'slug', 'name', 'mode', 'description', 'owner_screen_name', 'owner_id'],
            require_auth=True
        )

    @property
    def lists_all(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/list
            :allowed_param:'screen_name', 'user_id'
        """
        return bind_api(
            api=self,
            path='/lists/list.json',
            payload_type='list', payload_list=True,
            allowed_param=['screen_name', 'user_id'],
            require_auth=True
        )

    @property
    def lists_memberships(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/memberships
            :allowed_param:'screen_name', 'user_id', 'filter_to_owned_lists', 'cursor'
        """
        return bind_api(
            api=self,
            path='/lists/memberships.json',
            payload_type='list', payload_list=True,
            allowed_param=['screen_name', 'user_id', 'filter_to_owned_lists', 'cursor'],
            require_auth=True
        )

    @property
    def lists_subscriptions(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/subscriptions
            :allowed_param:'screen_name', 'user_id', 'cursor'
        """
        return bind_api(
            api=self,
            path='/lists/subscriptions.json',
            payload_type='list', payload_list=True,
            allowed_param=['screen_name', 'user_id', 'cursor'],
            require_auth=True
        )

    @property
    def list_timeline(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/statuses
            :allowed_param:'owner_screen_name', 'slug', 'owner_id', 'list_id',
             'since_id', 'max_id', 'count', 'include_rts
        """
        return bind_api(
            api=self,
            path='/lists/statuses.json',
            payload_type='status', payload_list=True,
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id', 'since_id', 'max_id', 'count',
                           'include_rts']
        )

    @property
    def get_list(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/lists/show
            :allowed_param:'owner_screen_name', 'owner_id', 'slug', 'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/show.json',
            payload_type='list',
            allowed_param=['owner_screen_name', 'owner_id', 'slug', 'list_id']
        )

    @property
    def add_list_member(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/create
            :allowed_param:'screen_name', 'user_id', 'owner_screen_name',
             'owner_id', 'slug', 'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/members/create.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'owner_screen_name',
                           'owner_id', 'slug', 'list_id'],
            require_auth=True
        )

    @property
    def remove_list_member(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/destroy
            :allowed_param:'screen_name', 'user_id', 'owner_screen_name',
             'owner_id', 'slug', 'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/members/destroy.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'owner_screen_name',
                           'owner_id', 'slug', 'list_id'],
            require_auth=True
        )

    def add_list_members(self, screen_name=None, user_id=None, slug=None,
                         list_id=None, owner_id=None, owner_screen_name=None):
        """ Perform bulk add of list members from user ID or screenname """
        return self._add_list_members(list_to_csv(screen_name),
                                      list_to_csv(user_id),
                                      slug, list_id, owner_id,
                                      owner_screen_name)

    @property
    def _add_list_members(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/create_all
            :allowed_param:'screen_name', 'user_id', 'slug', 'list_id',
            'owner_id', 'owner_screen_name'

        """
        return bind_api(
            api=self,
            path='/lists/members/create_all.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'slug', 'list_id',
                           'owner_id', 'owner_screen_name'],
            require_auth=True
        )

    def remove_list_members(self, screen_name=None, user_id=None, slug=None,
                            list_id=None, owner_id=None, owner_screen_name=None):
        """ Perform bulk remove of list members from user ID or screenname """
        return self._remove_list_members(list_to_csv(screen_name),
                                         list_to_csv(user_id),
                                         slug, list_id, owner_id,
                                         owner_screen_name)

    @property
    def _remove_list_members(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/members/destroy_all
            :allowed_param:'screen_name', 'user_id', 'slug', 'list_id',
            'owner_id', 'owner_screen_name'

        """
        return bind_api(
            api=self,
            path='/lists/members/destroy_all.json',
            method='POST',
            payload_type='list',
            allowed_param=['screen_name', 'user_id', 'slug', 'list_id',
                           'owner_id', 'owner_screen_name'],
            require_auth=True
        )

    @property
    def list_members(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/members
            :allowed_param:'owner_screen_name', 'slug', 'list_id',
             'owner_id', 'cursor
        """
        return bind_api(
            api=self,
            path='/lists/members.json',
            payload_type='user', payload_list=True,
            allowed_param=['owner_screen_name', 'slug', 'list_id',
                           'owner_id', 'cursor']
        )

    @property
    def show_list_member(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/members/show
            :allowed_param:'list_id', 'slug', 'user_id', 'screen_name',
             'owner_screen_name', 'owner_id
        """
        return bind_api(
            api=self,
            path='/lists/members/show.json',
            payload_type='user',
            allowed_param=['list_id', 'slug', 'user_id', 'screen_name',
                           'owner_screen_name', 'owner_id']
        )

    @property
    def subscribe_list(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/subscribers/create
            :allowed_param:'owner_screen_name', 'slug', 'owner_id',
            'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/subscribers/create.json',
            method='POST',
            payload_type='list',
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id'],
            require_auth=True
        )

    @property
    def unsubscribe_list(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/post/lists/subscribers/destroy
            :allowed_param:'owner_screen_name', 'slug', 'owner_id',
            'list_id'
        """
        return bind_api(
            api=self,
            path='/lists/subscribers/destroy.json',
            method='POST',
            payload_type='list',
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id'],
            require_auth=True
        )

    @property
    def list_subscribers(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/subscribers
            :allowed_param:'owner_screen_name', 'slug', 'owner_id',
             'list_id', 'cursor
        """
        return bind_api(
            api=self,
            path='/lists/subscribers.json',
            payload_type='user', payload_list=True,
            allowed_param=['owner_screen_name', 'slug', 'owner_id',
                           'list_id', 'cursor']
        )

    @property
    def show_list_subscriber(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/lists/subscribers/show
            :allowed_param:'owner_screen_name', 'slug', 'screen_name',
             'owner_id', 'list_id', 'user_id
        """
        return bind_api(
            api=self,
            path='/lists/subscribers/show.json',
            payload_type='user',
            allowed_param=['owner_screen_name', 'slug', 'screen_name',
                           'owner_id', 'list_id', 'user_id']
        )

    @property
    def trends_available(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/trends/available """
        return bind_api(
            api=self,
            path='/trends/available.json',
            payload_type='json'
        )

    @property
    def trends_place(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/trends/place
            :allowed_param:'id', 'exclude'
        """
        return bind_api(
            api=self,
            path='/trends/place.json',
            payload_type='json',
            allowed_param=['id', 'exclude']
        )

    @property
    def trends_closest(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/trends/closest
            :allowed_param:'lat', 'long'
        """
        return bind_api(
            api=self,
            path='/trends/closest.json',
            payload_type='json',
            allowed_param=['lat', 'long']
        )

    @property
    def search(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/search/tweets
            :allowed_param:'q', 'lang', 'locale', 'since_id', 'geocode',
             'max_id', 'since', 'until', 'result_type', 'count',
              'include_entities', 'from', 'to', 'source'
        """
        return bind_api(
            api=self,
            path='/search/tweets.json',
            payload_type='search_results',
            allowed_param=['q', 'lang', 'locale', 'since_id', 'geocode',
                           'max_id', 'since', 'until', 'result_type',
                           'count', 'include_entities', 'from',
                           'to', 'source']
        )

    @property
    def reverse_geocode(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/geo/reverse_geocode
            :allowed_param:'lat', 'long', 'accuracy', 'granularity', 'max_results'
        """
        return bind_api(
            api=self,
            path='/geo/reverse_geocode.json',
            payload_type='place', payload_list=True,
            allowed_param=['lat', 'long', 'accuracy', 'granularity',
                           'max_results']
        )

    @property
    def geo_id(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/geo/id/%3Aplace_id
            :allowed_param:'id'
        """
        return bind_api(
            api=self,
            path='/geo/id/{id}.json',
            payload_type='place',
            allowed_param=['id']
        )

    @property
    def geo_search(self):
        """ :reference: https://dev.twitter.com/docs/api/1.1/get/geo/search
            :allowed_param:'lat', 'long', 'query', 'ip', 'granularity',
             'accuracy', 'max_results', 'contained_within

        """
        return bind_api(
            api=self,
            path='/geo/search.json',
            payload_type='place', payload_list=True,
            allowed_param=['lat', 'long', 'query', 'ip', 'granularity',
                           'accuracy', 'max_results', 'contained_within']
        )

    @property
    def geo_similar_places(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/geo/similar_places
            :allowed_param:'lat', 'long', 'name', 'contained_within'
        """
        return bind_api(
            api=self,
            path='/geo/similar_places.json',
            payload_type='place', payload_list=True,
            allowed_param=['lat', 'long', 'name', 'contained_within']
        )

    @property
    def supported_languages(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/help/languages """
        return bind_api(
            api=self,
            path='/help/languages.json',
            payload_type='json',
            require_auth=True
        )

    @property
    def configuration(self):
        """ :reference: https://dev.twitter.com/rest/reference/get/help/configuration """
        return bind_api(
            api=self,
            path='/help/configuration.json',
            payload_type='json',
            require_auth=True
        )

    """ Internal use only """

    @staticmethod
    def _pack_image(filename, max_size, form_field="image", f=None):
        """Pack image from file into multipart-formdata post body"""
        # image must be less than 700kb in size
        if f is None:
            try:
                if os.path.getsize(filename) > (max_size * 1024):
                    raise TweepError('File is too big, must be less than %skb.' % max_size)
            except os.error as e:
                raise TweepError('Unable to access file: %s' % e.strerror)

            # build the mulitpart-formdata body
            fp = open(filename, 'rb')
        else:
            f.seek(0, 2)  # Seek to end of file
            if f.tell() > (max_size * 1024):
                raise TweepError('File is too big, must be less than %skb.' % max_size)
            f.seek(0)  # Reset to beginning of file
            fp = f

        # image must be gif, jpeg, or png
        file_type = mimetypes.guess_type(filename)
        if file_type is None:
            raise TweepError('Could not determine file type')
        file_type = file_type[0]
        if file_type not in ['image/gif', 'image/jpeg', 'image/png']:
            raise TweepError('Invalid file type for image: %s' % file_type)

        if isinstance(filename, six.text_type):
            filename = filename.encode("utf-8")

        BOUNDARY = b'Tw3ePy'
        body = []
        body.append(b'--' + BOUNDARY)
        body.append('Content-Disposition: form-data; name="{0}";'
                    ' filename="{1}"'.format(form_field, filename)
                    .encode('utf-8'))
        body.append('Content-Type: {0}'.format(file_type).encode('utf-8'))
        body.append(b'')
        body.append(fp.read())
        body.append(b'--' + BOUNDARY + b'--')
        body.append(b'')
        fp.close()
        body = b'\r\n'.join(body)

        # build headers
        headers = {
            'Content-Type': 'multipart/form-data; boundary=Tw3ePy',
            'Content-Length': str(len(body))
        }

        return headers, body
