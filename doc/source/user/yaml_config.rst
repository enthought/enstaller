==================
YAML configuration
==================

Enstaller now supports a new configuration format, using the YAML syntax.
Currently, you have to explicitly specify the configuration file path to
use this format::

    enpkg -c <...>/enstaller.yaml ...

The YAML-based configuration is more consistent, and simpler to read/write as a
human than the legacy format.

.. note:: this format is still experimental, and may change without notice.

Basic example
=============

This is a fairly complete example of available settings in the YAML
format:

.. code-block:: yaml

    # Which server to use to connect to
    store_url: "https://api.enthought.com"

    # Whether to enforce SSL CA verification
    verify_ssl: false

    # List of <organization>/<repository>
    repositories:
      - "enthought/commercial"
      - "enthought/free"
      # Local FS repository -- should be a directory, and an index.json is expected
      # in that directory
      - "file:///foo"

    # Authentication
    authentication:
      api_token: <your_api_token>

    # Directory to use to cache eggs
    files_cache: "~/.cached_eggs/{PLATFORM}"

Authentication
==============

One can select plain-text authentication (insecure):

.. code-block:: yaml

    # Authentication
    authentication:
      kind: simple
      username: <your_username>
      password: <your_password>

or token-based:

.. code-block:: yaml

    authentication:
      # kind is optional as api_token is the default
      kind: token
      api_token: <your_token>

Tokens should still be hold secret, but are more secure than password because
you can revoke tokens.
