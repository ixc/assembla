import urllib
import requests
import json
import datetime
from assembla.lib import AssemblaObject, assembla_filter
import settings
import time

__VERSION__ = '2.1.1'

class API(object):
    cache_responses = False
    cache = {}

    def __init__(self, key=None, secret=None):
        """
        :key,
        :secret
            Your Assembla API access details, available from
            https://www.assembla.com/user/edit/manage_clients
        """
        if not key or not secret:
            raise Exception(
                'The Assembla API requires your API \'key\' and \'secret\', '
                'accessible from https://www.assembla.com/user/edit/manage_clients'
            )
        self.key = key
        self.secret = secret
        self.session = requests.Session()

    @assembla_filter
    def stream(self):
        """
        All Events available
        """
        return self._get_json(Event)

    @assembla_filter
    def spaces(self):
        """
        All Spaces available
        """
        return self._get_json(Space)

    def user(self, id):
        """
        Records for a given user available
        """
        return self._get_json(model=User, rel_path="%s/%s" % (User.rel_path, id), single=True)

    def _get_json(self, model, space=None, rel_path=None, extra_params=None, single=False):
        """
        Base level method which does all the work of hitting the API
        """

        # Only API.spaces and API.event should not provide
        # the `space argument
        if space is None and model not in (Space, Event, User):
            raise Exception(
                'In general, `API._get_json` should always '
                'be called with a `space` argument.'
            )

        if not extra_params:
            extra_params = {}

        # Handle pagination for requests carrying large amounts of data
        if model.can_paginate:
            extra_params['page'] = extra_params.get('page', 1)

        # Generate the url to hit
        url = '{0}/{1}/{2}.json?{3}'.format(
            settings.API_ROOT_PATH,
            settings.API_VERSION,
            rel_path or model.rel_path,
            urllib.urlencode(extra_params),
        )

        # If the cache is being used and the url has been hit already
        if self.cache_responses and url in self.cache:
            response = self.cache[url]
        else:
            # Fetch the data
            try:
                headers = {'X-Api-Key': self.key, 'X-Api-Secret': self.secret}
                response = self.session.get(url=url, headers=headers)
                # If the cache is being used, update it
                if self.cache_responses:
                    self.cache[url] = response
            except requests.ConnectionError, e:
                print '\033[91m' + "Request to %s failed - skipping." % url + '\033[0m'
                print unicode(datetime.datetime.now())
                print e

                if single:
                    return {}
                else:
                    return []


        if response.status_code == 200:  # OK
            if single:
                instance = model(data=response.json())
                instance.api = self
                if space:
                    instance.space = space
                return instance
            else:
                results = []
                for json in response.json():
                    instance=model(data=json)
                    instance.api = self
                    if space:
                        instance.space = space
                    results.append(instance)

                # if the #results on this page == limit per page, then fetch the next page to see if there's any more results
                per_page = extra_params.get('per_page', 10) #10 = assembla's default for tickets, ticket comments. Does this vary by model?
                if len(results) == per_page and model.can_paginate:
                    extra_params['page'] = extra_params['page'] + 1
                    next_results = self._get_json(model, space, rel_path, extra_params)
                    results = results + next_results

                return results
        elif response.status_code == 204:  # No Content
            if single:
                return {}
            else:
                return []
        else:  # Most likely a 404 Not Found
            raise Exception(
                'Code {0} returned from `{1}`. Response text: "{2}".'.format(
                    response.status_code,
                    url,
                    response.text
                )
            )

    def _post_json(self, instance, space=None, rel_path=None, extra_params=None):
        """
        Base level method which does all the work of hitting the API
        """

        model = type(instance)

        # Only API.spaces and API.event should not provide
        # the `space argument
        if space is None and model not in (Space, Event):
            raise Exception(
                'In general, `API._post_json` should always '
                'be called with a `space` argument.'
            )

        if 'number' in instance.data:
            raise AttributeError(
                'You cannot create a ticket which already has a number'
            )

        if not extra_params:
            extra_params = {}

        # Generate the url to hit
        url = '{0}/{1}/{2}?{3}'.format(
            settings.API_ROOT_PATH,
            settings.API_VERSION,
            rel_path or model.rel_path,
            urllib.urlencode(extra_params),
        )

        # Fetch the data
        response = requests.post(
            url=url,
            data=json.dumps(instance.data),
            headers={
                'X-Api-Key': self.key,
                'X-Api-Secret': self.secret,
                'Content-type': "application/json",
            },
        )

        if response.status_code == 201:  # OK
            instance=model(data=response.json())
            instance.api = self
            if space:
                instance.space = space
            return instance
        else:  # Most likely a 404 Not Found
            raise Exception(
                'Code {0} returned from `{1}`. Response text: "{2}".'.format(
                    response.status_code,
                    url,
                    response.text
                )
            )


    def _delete_json(self, instance, space=None, rel_path=None, extra_params=None):
        """
        Base level method which does all the work of hitting the API
        """

        # Only API.spaces and API.event should not provide
        # the `space argument
        if space is None and model not in (Space, Event):
            raise Exception(
                'In general, `API._delete_json` should always '
                'be called with a `space` argument.'
            )

        if 'number' not in instance.data:
            raise AttributeError(
                'You cannot delete a ticket which doesn\'t have a number'
            )

        if not extra_params:
            extra_params = {}

        # Generate the url to hit
        url = '{0}/{1}/{2}/{3}.json?{4}'.format(
            settings.API_ROOT_PATH,
            settings.API_VERSION,
            rel_path or model.rel_path,
            instance['number'],
            urllib.urlencode(extra_params),
        )

        # Fetch the data
        response = requests.delete(
            url=url,
            headers={
                'X-Api-Key': self.key,
                'X-Api-Secret': self.secret,
                'Content-type': "application/json",
            },
        )

        if response.status_code == 204:  # OK
            return True
        else:  # Most likely a 404 Not Found
            raise Exception(
                'Code {0} returned from `{1}`. Response text: "{2}".'.format(
                    response.status_code,
                    url,
                    response.text
                )
            )

    def _put_json(self, instance, space=None, rel_path=None, extra_params=None):
        """
        Base level method which does all the work of hitting the API
        """

        model = type(instance)

        # Only API.spaces and API.event should not provide
        # the `space argument
        if space is None and model not in (Space, Event):
            raise Exception(
                'In general, `API._put_json` should always '
                'be called with a `space` argument.'
            )

        if not extra_params:
            extra_params = {}

        # Generate the url to hit
        url = '{0}/{1}/{2}/{3}.json?{4}'.format(
            settings.API_ROOT_PATH,
            settings.API_VERSION,
            rel_path or model.rel_path,
            instance['number'],
            urllib.urlencode(extra_params),
        )

        # Fetch the data
        response = requests.put(
            url=url,
            data=json.dumps(instance.data),
            headers={
                'X-Api-Key': self.key,
                'X-Api-Secret': self.secret,
                'Content-type': "application/json",
            },
        )

        if response.status_code == 204:  # OK
            return instance
        else:  # Most likely a 404 Not Found
            raise Exception(
                'Code {0} returned from `{1}`. Response text: "{2}".'.format(
                    response.status_code,
                    url,
                    response.text
                )
            )

    def _bind_variables(self, instance, space):
        """
        Bind related variables to the instance
        """
        instance.api = self
        if space:
            instance.space = space
        return instance


class Event(AssemblaObject):
    rel_path = 'activity'


class Space(AssemblaObject):
    rel_path = 'spaces'

    @assembla_filter
    def tickets(self):
        """
        All Tickets in this Space
        """
        return self.api._get_json(
            Ticket,
            space=self,
            rel_path=self._build_rel_path('tickets'),
            extra_params={
                'per_page': 100,
                'report': 0  # All tickets
            }
        )

    @assembla_filter
    def milestones(self):
        """
        All Milestones in this Space
        """
        return self.api._get_json(
            Milestone,
            space=self,
            rel_path=self._build_rel_path('milestones/all'),
        )

    @assembla_filter
    def components(self):
        """"
        All components in this Space
        """
        return self.api._get_json(
            Component,
            space=self,
            rel_path=self._build_rel_path('ticket_components'),
        )

    @assembla_filter
    def users(self):
        """
        All Users with access to this Space
        """
        return self.api._get_json(
            User,
            space=self,
            rel_path=self._build_rel_path('users'),
        )

    def _build_rel_path(self, to_append=None):
        """
        Build a relative path to the API endpoint
        """
        return '{0}/{1}/{2}'.format(
            self.rel_path,
            self['id'],
            to_append if to_append else ''
        )


class Component(AssemblaObject):
    pass


class Milestone(AssemblaObject):
    @assembla_filter
    def tickets(self):
        """
        All Tickets which are a part of this Milestone
        """
        return filter(
            lambda ticket: ticket.get('milestone_id', None) == self['id'],
            self.space.tickets()
        )


class Ticket(AssemblaObject):

    @property
    def milestone(self):
        """
        The Milestone that the Ticket is a part of
        """
        if self.get('milestone_id', None):
            milestones = filter(
                lambda milestone: milestone['id'] == self['milestone_id'],
                self.space.milestones()
            )
            if milestones:
                return milestones[0]

    @property
    def user(self):
        """
        The User currently assigned to the Ticket
        """
        if self.get('assigned_to_id', None):
            users = filter(
                lambda user: user['id'] == self['assigned_to_id'],
                self.space.users()
            )
            if users:
                return users[0]

    @property
    def component(self):
        """
        The Component currently assigned to the Ticket
        """
        if self.get('component_id', None):
            components = filter(
                lambda component: component['id'] == self['component_id'],
                self.space.components()
            )
            if components:
                return components[0]
                
    @assembla_filter
    def comments(self):
        """
        The Comments associated to this Ticket
        """
        
        #I did not use _build_rel_path because Ticket don't have rel_path
        rel_path = 'spaces/%s/tickets/%s/ticket_comments' % (self.space['id'], self['number'])
        return self.api._get_json(
            Comment,
            space=self.space,
            rel_path=rel_path,
            extra_params={
                'per_page': 100
            }
        )        

    def write(self):
        try:
            self.api = self.space.api
        except AttributeError:
            raise AttributeError("A ticket must have a 'space' attribute before you can write it to Assembla.")

        if self.get('number'): #we are modifying an existing ticket
            return self.api._put_json(
                self,
                space=self.space,
                rel_path=self.space._build_rel_path('tickets'),
            )
        else: #creating a new ticketi
            return self.api._post_json(
                self,
                space=self.space,
                rel_path=self.space._build_rel_path('tickets'),
            )

    def delete(self):
        try:
            self.api = self.space.api
        except AttributeError:
            raise AttributeError("A ticket must have a 'space' attribute before you can write it to Assembla.")

        return self.api._delete_json(
            self,
            space=self.space,
            rel_path=self.space._build_rel_path('tickets'),
        )


class Comment(AssemblaObject):
    pass


class User(AssemblaObject):
    rel_path = "users"
    can_paginate = False

    @assembla_filter
    def tickets(self):
        """
        A User's tickets across all available spaces
        """
        tickets = []
        for space in self.api.spaces():
            tickets += filter(
                lambda ticket: ticket.get('assigned_to_id', None) == self['id'],
                space.tickets()
            )
        return tickets
