========
Examples
========

This section highlights the main APIs through some simple examples.

Package search/listing
=======================

Most search, listing operations in enstaller are done through
:py:class:`~enstaller.repository.Repository` instances, which are
containers of package metadata. For example, to list every egg installed
in sys.prefix::

    from enstaller import Repository

    repository = Repository._from_prefixes([sys.prefix])
    for package in repository.iter_packages():
        print("{0}-{1}".format(package.name, package.version))

one can also list the most recent version for each package::

    for package in repository.iter_most_recent_packages():
        print("{0}-{1}".format(package.name, package.version))

:py:class:`~.enstaller.repository.Repository` instances are "dumb" containers,
and don't handle network connections, authentication, etc... A simple way to
create a "real" repository is to start from a set of eggs::

    from enstaller import Repository, RepositoryPackageMetadata

    repository = Repository()
    for path in glob.glob("*.egg"):
        package = RepositoryPackageMetadata.from_egg(path)
        repository.add_package(package)

We will later look into creating repositories from old-style repositories
(as created by epd-repo) or brood repositories. The simplicity of
repositories allows loose-coupling between operations on a repository and
the package metadata origin.

Connecting and authenticating
=============================

Http connections are handled through :py:class:`~enstaller.session.Session`
objects. To start a session, one may simply do::

    from enstaller Configuration, Session

    configuration = Configuration()
    configuration.update(auth=("username", "password"))

    session = Session.authenticated_from_configuration(configuration)

:py:class:`~enstaller.session.Session` are thin wrappers around requests'
Session. Its main features over requests' Session are etag handling,
``file://`` uri handling, pluggable authentication method as well as
integration with :py:class:`~enstaller.config.Configuration` instances for
settings (proxy, etc...).

In addition to head/get/post methods, :py:class:`~enstaller.session.Session`
instances have a slighly higher-level download method, which enables streaming
and raises an exception if an HTTP error occurs, and is robust against
stalled/cancelled downloads::

    # target is the path for the created file. Will not exist if download fails
    # (including cancelled by e.g. `Ctr+C`).
    target = session.download(some_url)

Delayed authenticated sessions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If one needs to authenticate the session later than creation time, e.g. if the
auth information is set up in the configuration, that's possible as follows::

    from enstaller Configuration, Session

    configuration = Configuration()
    session = Session.from_configuration(configuration)

    # Prompt the user for authentication, etc...
    ...

    configuration.update(auth=("username", "password"))
    session.authenticate(configuration.auth)

Creating remote repositories
============================

To create repositories from our legacy index.json formats, one can use the
repository_factory method from enstaller.legacy_stores::

    from enstaller import Configuration, Session
    from enstaller.legacy_stores import repository_factory

    config = Configuration._from_legacy_locations()

    session = Session.from_configuration(config)
    session.authenticate(config.auth)

    remote_repository = repository_factory(session, config.indices)

    # Same, with etag-based caching
    with session.etag():
        remote_repository = repository_factory(session, config.indices)

.. note:: this works for both use_webservice enabled and disabled:

        * when enabled, config.indices returns a one item-list of (index,
          store) pair corresponding to the canopy-style index, whereas
        * when disabled, config.indices returns a list of pairs (index, store),
          one pair per entry in IndexedRepos.

Solving dependencies
====================

The dependency solver has a simple API to resolve dependencies::

    from enstaller.solver import Request, Requirement, Solver

    # represents the set of packages available
    remote_repository = Repository(...)
    # represents the set of packages currently installed
    installed_repository = Repository(...)

    solver = Solver(remote_repository, installed_repository)

    request = Request()
    request.install(Requirement.from_anything("numpy"))
    request.install(Requirement.from_anything("ipython"))

    # actions are (opcode, egg) pairs
    # WARNING: this is likely to change
    actions = solver.resolve(request)

.. note:: actions returned by the solver are only of the install/remove
   type, fetching is handled outside the solver.

Executor
========

.. Needs APIs to convert solver actions into executor actions, + 
