YAML configuration
==================

Enstaller now supports a new configuration format, using the YAML syntax.
Currently, you have to explicitly specify the configuration file path to
use this format::

    enpkg -c <...>/enstaller.yaml ...

Format
------

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

    # Authentication
    authentication:
      username: "foo@enthought.com"
      password: "password"

    # Directory to use to cache eggs
    files_cache: "~/.cached_eggs/{PLATFORM}"
