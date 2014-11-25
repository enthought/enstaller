import os.path

from egginst._compat import PY2
from egginst.vendor.six import string_types

from enstaller.auth import APITokenAuth, UserPasswordAuth
from enstaller.errors import InvalidConfiguration
from enstaller.plat import custom_plat
from enstaller.vendor import jsonschema

if PY2:
    from enstaller.vendor import yaml
else:
    from enstaller.vendor import yaml_py3 as yaml


_API_TOKEN = "api_token"
_AUTHENTICATION = "authentication"
_AUTHENTICATION_TYPE = "kind"
_AUTHENTICATION_TYPE_BASIC = "basic"
_AUTHENTICATION_TYPE_SIMPLE = "simple"
_AUTHENTICATION_TYPE_TOKEN = "token"
_MAX_RETRIES = "max_retries"
_SSL_VERIFY = "verify_ssl"
_USERNAME = "username"
_PASSWORD = "password"
_AUTH_STRING = "auth"
_REPOSITORIES = "repositories"
_FILES_CACHE = "files_cache"
_STORE_URL = "store_url"

_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "EnstallerConfiguration",
    "description": "Enstaller >= 4.8.0 configuration",
    "type": "object",
    "properties": {
        "max_retries": {
            "description": "Max number of time to retry connecting to a "
                           "remote server or re-fetching data with invalid "
                           "checksum",
            "type": "integer"
        },
        "verify_ssl": {
            "description": "Whether to actually check SSL CA certificate or "
                           "not",
            "type": "boolean"
        },
        "store_url": {
            "description": "The url (schema + hostname only of the store to "
                           "connect to).",
            "type": "string"
        },
        "files_cache": {
            "description": "Where to cache downloaded files.",
            "type": "string"
        },
        "authentication": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/definitions/api_token_authentication"},
                {"$ref": "#/definitions/simple_authentication"},
                {"$ref": "#/definitions/basic_authentication"}
            ],
            "description": "Authentication."
        },
        "repositories": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of repositories."
        }
    },
    "definitions": {
        "api_token_authentication": {
            "properties": {
                "kind": {
                    "enum": [_AUTHENTICATION_TYPE_TOKEN],
                    "default": _AUTHENTICATION_TYPE_TOKEN
                },
                _API_TOKEN: {"type": "string"}
            },
            "required": [_API_TOKEN],
            "additionalProperties": False
        },
        "simple_authentication": {
            "properties": {
                "kind": {
                    "enum": [_AUTHENTICATION_TYPE_SIMPLE]
                },
                _USERNAME: {"type": "string"},
                _PASSWORD: {"type": "string"}
            },
            "required": ["kind", _USERNAME, _PASSWORD],
            "additionalProperties": False
        },
        "basic_authentication": {
            "properties": {
                "kind": {
                    "enum": [_AUTHENTICATION_TYPE_BASIC]
                },
                _AUTH_STRING: {"type": "string"}
            },
            "required": ["kind", _AUTH_STRING],
            "additionalProperties": False
        }
    },
    "additionalProperties": False,
}


def load_configuration_from_yaml(cls, filename_or_fp):
    # FIXME: local import to workaround circular import
    from enstaller.config import STORE_KIND_BROOD
    if isinstance(filename_or_fp, string_types):
        with open(filename_or_fp, "rt") as fp:
            data = yaml.load(fp)
    else:
        data = yaml.load(filename_or_fp)

    if data is None:
        data = {}
    else:
        try:
            jsonschema.validate(data, _SCHEMA)
        except jsonschema.ValidationError as e:
            msg = "Invalid configuration: {0!r}".format(e.message)
            raise InvalidConfiguration(msg)

    config = cls()

    if _AUTHENTICATION in data:
        authentication = data[_AUTHENTICATION]
        authentication_type = authentication.get(_AUTHENTICATION_TYPE,
                                                 _AUTHENTICATION_TYPE_TOKEN)
        if authentication_type == _AUTHENTICATION_TYPE_SIMPLE:
            username = authentication[_USERNAME]
            password = authentication[_PASSWORD]
            auth = UserPasswordAuth(username, password)
        elif authentication_type == _AUTHENTICATION_TYPE_BASIC:
            auth_string = authentication[_AUTH_STRING]
            auth = UserPasswordAuth.from_encoded_auth(auth_string)
        elif authentication_type == _AUTHENTICATION_TYPE_TOKEN:
            token = authentication[_API_TOKEN]
            auth = APITokenAuth(token)
        else:
            msg = "Unknown authentication type {0!r}". \
                  format(authentication_type)
            raise InvalidConfiguration(msg)
        config.update(auth=auth)

    if _STORE_URL in data:
        config.update(store_url=data[_STORE_URL])
    if _REPOSITORIES in data:
        config.set_repositories_from_names(data[_REPOSITORIES])

    if _FILES_CACHE in data:
        files_cache = os.path.expanduser(data[_FILES_CACHE]). \
            replace("{PLATFORM}", custom_plat)
        config._repository_cache = files_cache
    if _MAX_RETRIES in data:
        config.update(max_retries=data[_MAX_RETRIES])
    if _SSL_VERIFY in data and not data[_SSL_VERIFY]:
        config.update(verify_ssl=data[_SSL_VERIFY])

    config.update(use_webservice=False)

    if isinstance(filename_or_fp, string_types):
        config._filename = filename_or_fp

    config._store_kind = STORE_KIND_BROOD
    return config
