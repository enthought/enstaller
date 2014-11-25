INSTALL_SCHEMA = {
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
        "requirement": {
            "description": "The package requirement",
            "type": "string"
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
    "required": ["authentication", "requirement"]
}
