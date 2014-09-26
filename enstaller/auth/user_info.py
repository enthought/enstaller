import json

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
