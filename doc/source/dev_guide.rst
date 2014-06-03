=========
Dev guide
=========

The fundamental concepts in enstaller are repositories, solvers and installers.

Repositories are containers of metadata, and may be used to query package
information. Repositories may be created from remote locations (e.g. our
packages on api.enthought.com), or local locations (e.g. eggs installed in
sys.prefix)

Solvers transform a request (e.g. 'install scipy') into a set of actions
required to fullfill that request. It resolve dependencies and so on to keep
the system consistent.

An installer's responsibility is to transform a binary artefact (e.g. an egg
file) into its installed form: it extract files, apply pre/post install
scripts, etc... There is currently only one installer in enpkg, the egginst
installer.

Repository
==========

Repositories are simple containers of package metadata. They know as little as
possible about the package metadata themselves: conceptually, the only required
metadata for each package are name and version.

Creating repositories
---------------------

The _from_prefixes contructor create a new repository from a list of prefixes,
by parsing the metadata in the EGG-INFO directory inside each prefix::

    # Create a repository representing installed eggs
    repository = Repository._from_prefixes([sys.prefix])

You can also easily create a repository from a set of eggs, by using the
RepositoryPackageMetadata class::

    # Create a repository to query metadata from a directory full of eggs
    repository = Repository()

    for path in glob.glob("*.egg"):
        package = RepositoryPackageMetadata.from_egg(path)
        repository.add_package(package)

To create a repository from our legacy repositories on api.e.com, there is a
helper ``legacy_index_parser`` which generates ``RepositoryPackageMetadata``
instances::

    # Create a configuration from an existing '~/.enstaller4rc'
    config = Configuration._get_default_config()

    repository = Repository()
    for package in legacy_index_parser(config):
        repository.add_package(package)

Note: the package metadata returned by repositories are not always consistent.
For example, if you create a repository with _from_prefixes, the repository
will contain instances of InstalledPackageMetadata, not
RepositoryPackageMetadata.

Querying repositories
---------------------

Once you have a repository, you can query packages contained in it.

The simplest way to query a repository is to iterate over it::

    # Print the name/version of each package
    for package in repository.iter_packages():
        print package.name, package.full_version

We may want to only show the most recent version of each package::

    # Only show the most recent version of each package in the repository
    for package in sorted(repository.iter_most_recent_packages()):
        print package.name, package.full_version

To see the available versions of a given package, say 'numpy'::

    for package in package.find_packages("numpy"):
        print package.name, package.full_version
