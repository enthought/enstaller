from __future__ import absolute_import

import json

from enstaller.errors import AuthFailedError
from enstaller.vendor import requests


class UserInfo(object):
    @classmethod
    def from_json_string(cls, s):
        return cls.from_json(json.loads(s))

    @classmethod
    def from_json(cls, json_data):
        return cls(json_data["is_authenticated"],
                   json_data["first_name"],
                   json_data["last_name"],
                   json_data["has_subscription"],
                   json_data["subscription_level"])

    @classmethod
    def from_session(cls, session):
        """
        Returns the user information.

        The session must be authenticated.

        Parameters
        ----------
        session : Session
            An enstaller session, used to connect to the server to get user
            information.
        """
        # FIXME: circular import
        from .auth_managers import LegacyCanopyAuthManager

        if isinstance(session._authenticator, LegacyCanopyAuthManager):
            try:
                resp = session.get(session._authenticator.url)
            except requests.exceptions.ConnectionError as e:
                raise AuthFailedError(e)

            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise AuthFailedError("Authentication error: %r" % str(e))

            return cls.from_json_string(resp.content.decode("utf8"))
        else:
            return cls(True)

    def __init__(self, is_authenticated, first_name="", last_name="",
                 has_subscription=False, subscription_level="free"):
        self.is_authenticated = is_authenticated
        self.first_name = first_name
        self.last_name = last_name
        self.has_subscription = has_subscription
        self._subscription_level = subscription_level

    @property
    def subscription_level(self):
        if self.is_authenticated and self.has_subscription:
            return 'Canopy / EPD Basic or above'
        elif self.is_authenticated and not self.has_subscription:
            return 'Canopy / EPD Free'
        else:
            return None

    def to_dict(self):
        keys = (
            "is_authenticated",
            "first_name",
            "last_name",
            "has_subscription",
            "subscription_level",
        )
        return dict((k, getattr(self, k)) for k in keys)

    def __eq__(self, other):
        return self.to_dict() == other.to_dict()


DUMMY_USER = UserInfo(False)
