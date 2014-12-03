import copy


UPDATE_ALL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "install",
    "description": "machine CLI install args",
    "type": "object",
    "properties": {
        "authentication": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/definitions/simple_authentication"}
            ],
            "description": "Authentication."
        },
        "files_cache": {
            "description": "Where to cache downloaded files.",
            "type": "string"
        },
        "proxy": {
            "description": "Proxy setting (full URL).",
            "type": "string"
        },
        "repositories": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of repositories."
        },
        "store_url": {
            "description": "The url (schema + hostname only of the store to "
                           "connect to).",
            "type": "string"
        },
        "verify_ssl": {
            "description": "If false, SSL certificates are not validated "
                           "(INSECURE)",
            "type": "boolean"
        }
    },
    "definitions": {
        "simple_authentication": {
            "properties": {
                "kind": {
                    "enum": ["simple"]
                },
                "username": {"type": "string"},
                "password": {"type": "string"}
            },
            "required": ["kind", "username", "password"],
            "additionalProperties": False
        }
    },
    "additionalProperties": False,
    "required": ["authentication", "files_cache", "repositories",
                 "store_url"]
}

INSTALL_SCHEMA = copy.deepcopy(UPDATE_ALL_SCHEMA)
INSTALL_SCHEMA["required"] = [
    "authentication", "files_cache", "repositories", "requirement",
    "store_url"
]
INSTALL_SCHEMA["properties"].update({
    "requirement": {
        "description": "The package requirement",
        "type": "string"
    },
})
