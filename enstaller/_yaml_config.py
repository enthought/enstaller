import os.path

from egginst._compat import PY2, string_types

from enstaller.errors import InvalidConfiguration
from enstaller.plat import custom_plat
from enstaller.utils import fill_url
from enstaller.vendor import jsonschema

if PY2:
    from enstaller.vendor import yaml
else:
    from enstaller.vendor import yaml_py3 as yaml


_AUTHENTICATION = "authentication"
_AUTHENTICATION_TYPE = "type"
_AUTHENTICATION_TYPE_BASIC = "basic"
_AUTHENTICATION_TYPE_DIGEST = "digest"
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
        "store_url": {
            "description": "The url (schema + hostname only of the store to connect to).",  # noqa
            "type": "string"
        },
        "files_cache": {
            "description": "Where to cache downloaded files.",
            "type": "string"
        },
        "authentication": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/definitions/simple_authentication"},
                {"$ref": "#/definitions/digest_authentication"}
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
        "simple_authentication": {
            "properties": {
                "type": {
                    "enum": [_AUTHENTICATION_TYPE_BASIC],
                    "default": _AUTHENTICATION_TYPE_BASIC
                },
                _USERNAME: {"type": "string"},
                _PASSWORD: {"type": "string"}
            },
            "required": [_USERNAME, _PASSWORD],
            "additionalProperties": False
        },
        "digest_authentication": {
            "properties": {
                "type": {
                    "enum": [_AUTHENTICATION_TYPE_DIGEST]
                },
                _AUTH_STRING: {"type": "string"}
            },
            "required": ["type", _AUTH_STRING],
            "additionalProperties": False
        }
    },
    "additionalProperties": False,
}


def load_configuration_from_yaml(cls, filename_or_fp):
    # FIXME: local import to workaround circular import
    from enstaller.config import _decode_auth
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
                                                 _AUTHENTICATION_TYPE_BASIC)
        if authentication_type == _AUTHENTICATION_TYPE_BASIC:
            username = authentication[_USERNAME]
            password = authentication[_PASSWORD]
        elif authentication_type == _AUTHENTICATION_TYPE_DIGEST:
            username, password = _decode_auth(authentication[_AUTH_STRING])
        else:
            msg = "Unknown authentication type {0!r}". \
                  format(authentication_type)
            raise InvalidConfiguration(msg)
        config.set_auth(username, password)

    if _STORE_URL in data:
        config.set_store_url(data[_STORE_URL])
    if _REPOSITORIES in data:
        repository_urls = [
            config.store_url + "/repo/{}/{{PLATFORM}}".format(repository)
            for repository in data[_REPOSITORIES]
        ]
        config.set_indexed_repositories(repository_urls)
    if _FILES_CACHE in data:
        files_cache = os.path.expanduser(data[_FILES_CACHE]). \
            replace("{PLATFORM}", custom_plat)
        config._repository_cache = files_cache

    config.disable_webservice()

    if isinstance(filename_or_fp, string_types):
        config._filename = filename_or_fp
    return config
