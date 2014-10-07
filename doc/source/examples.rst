========
Examples
========

This section highlights the main APIs through some simple examples.

Package search/listing
=======================

Most search, listing operations in enstaller are done through
``Repository`` instances, which are containers of package metadata. For
example, to list every egg installed in sys.prefix::

    from enstaller.repository import Repository

    repository = Repository._from_prefixes([sys.prefix])
    for package in repository.iter_packages():
        print("{0}-{1}".format(package.name, package.version))

one can also list the most recent version for each package::

    for package in repository.iter_most_recent_packages():
        print("{0}-{1}".format(package.name, package.version))

``Repository`` instances are "dumb" containers, and don't handle network
connections, authentication, etc... A simple way to create a "real"
repository is to start from a set of eggs::

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

Http connections are handled through ``Session`` objects. To start a
session, one may simply do::

    from enstaller.configuration import Configuration
    from enstaller.session import Session

    configuration = Configuration()
    session = Session.from_configuration(configuration)
    session.authenticate(configuration.auth)

``Session`` are thin wrappers around requests' Session. Its main features
over requests' Session are etag handling, ``file://`` uri handling,
pluggable authentication method as well as integration with
``Configuration`` instances for settings (proxy, etc...).

In addition to head/get/post methods, ``Session`` instances have a slighly
higher-level fetch method, which enables streaming and raises an exception
if an HTTP error occurs::

    from enstaller.fetch_utils import checked_content

    resp = session.fetch(some_url)
    # checked_content will automatically remove "foo.bin" if for any
    # reason the block within the context manager is interrupted
    # (exception, Ctrl+C)
    with checked_content("foo.bin", "wb") as fp:
        for chunk in resp.iter_content(1024):
            fp.write(chunk)

Creating remote repositories
============================

To create repositories from our index.json formats, one can do as follows::

    config = Configuration._from_legacy_locations()

    session = Session.from_configuration(config)
    session.authenticate(config.auth)

    def repository_factory(session, indices):
        repository = Repository()
        for url, store_location in indices:
            resp = session.fetch(url)
            data = resp.json()
            for package in parse_index(data, store_location):
                repository.add_package(package)
        return repository

    remote_repository = repository_factory(session, config.indices)

    # Same, with etag-based caching:
    with session.etag():
        remote_repository = repository_factory(session, config.indices)

Some API similar to repository_factory will appear at some point, once brood
integration is implemented.

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
