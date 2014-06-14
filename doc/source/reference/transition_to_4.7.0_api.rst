========================================
Dev guide for transitioning to 4.7.0 API
========================================

As the pre 4.7.0 API was fundamentally tied to module-level globals, we had to
change the internal enstaller API in a fundamental way. This guide explains how
to transition to the new API.

Configuration
=============

The enstaller.config module has been completely revamped:

* The main API is now the :py:class:`~enstaller.config.Configuration` class.
  Multiple instances of this class can coexist in the same process (though one
  may need to be careful about keyring-related interactions).
* Most individual methods of the module have been removed, and the information
  need to be accessed through the configuration object instead.

Creating configuration instances
--------------------------------

The most common way to create a configuration is to start from an existing
configuration file::

    config = Configuration.from_file(filename)
    print(config.use_webservice)

One can also create a configuration from the default location::

    config = Configuration._from_legacy_locations()

This API may be revised as we change the location logic (the current logic made
sense for an EPD-like setup, but does not anymore with virtualenvs).

Note: this will fail if no .enstaller4rc is found. To create a default
enstaller4rc, you should instead use the write_default_config function::

    filename = ...
    if not os.path.exists(filename):
        write_default_config(filename)

    config = Configuration.from_file(filename)

Replacing get_auth
------------------

As the get_auth function was implicitely sharing global state, it has been
removed. Instead of::

    # Obsolete
    from enstaller.config import get_auth
    print(get_auth())

you should use::

    config = Configuration._from_legacy_locations()
    print(config.auth)

.. note:: the authentication may not be setup, in which case config.auth may
    return an invalid configration. To check whether the authentication is valid,
    use the is_auth_configured property::

        config = Configuration._from_legacy_locations()
        if config.is_auth_configured:
            print(config.auth)

Changing authentication
-----------------------

Enstaller does not use keyring anymore to hold password securely. Instead, the
password is now always stored insecurely in the EPD_auth setting inside
.enstaller4rc.

For backward compatibility, enpkg will convert password stored in the keyring
back into .enstaller4rc automatically. To avoid keyring issues, keyring is
bundled inside enstaller.

We advise *not* to change authentication directly in .enstaller4rc, as changing
configuration file is user-hostile. Instead, applications using enstaller
library should store the authentication themselves, and set it up inside the
Configuration object through the Configuration.set_auth method.

The private methods Configuration._change_auth and
Configuration._checked_change_auth are there for convenience, but their usage
is discouraged.

.. note:: while keeping the password in clear in insecure, this is actually
    more secure as enstaller would before implicitely change from clear to
    secure and vice et versa depending on whether keyring was available to
    enstaller. The midterm solution is to use token-based authentication and
    never store password, but this will need some support server-side before
    being deployed.

Removed config module functions
-------------------------------

The following functions have been removed:

* clear_auth: obsolete with keyring removal
* clear_cache: there is no configuration state anymore, juse use a new
  Configuration instance.
* get_repository_cache use Configuration repository_cache attribute
* get: use correponding Configuration attributes instead
* read: use Configuration instance and its attributes
* web_auth: use authenticate instead
* write: use the write method from Configuration instead


Repositories and package metadata
=================================

Most of the store-related functionalities are now available through the
:py:class:`~enstaller.repository.Repository` class. See
:ref:`repository-guide-label` for more information.
