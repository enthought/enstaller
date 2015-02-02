from enstaller.package import PackageMetadata
from enstaller.repository import Repository
from enstaller.versions.enpkg import EnpkgVersion

from .package_parser import PrettyPackageStringParser


class RepositoryPackage(PackageMetadata):
    """ Like PackageMetadata, but attached to a repository. """
    @classmethod
    def from_package(cls, package, repository_info):
        return RepositoryPackage(package.key, package.name,
                                 package.version, package.packages,
                                 package.python, repository_info)

    def __init__(self, key, name, version, packages, python, repository_info):
        super(RepositoryPackage, self).__init__(key, name, version,
                                                packages, python)
        self._repository_info = repository_info

    def __repr__(self):
        return "RepositoryPackage('{0}-{1}', repo={2!r})".format(
            self.name, self.version, self.repository_info)

    @property
    def repository_info(self):
        return self._repository_info

    @property
    def _comp_key(self):
        return (super(RepositoryPackage, self)._comp_key +
                (self._repository_info,))


def parse_package_list(packages):
    parser = PrettyPackageStringParser(EnpkgVersion.from_string)

    for package_str in packages:
        package = parser.parse_to_package(package_str, "2.7")
        full_name = "{0} {1}".format(package.name, package.full_version)
        yield full_name, package


def repository_factory(package_names, repository_info, reference_packages):
    repository = Repository()
    for package_name in package_names:
        package = reference_packages[package_name]
        package = RepositoryPackage.from_package(package, repository_info)
        repository.add_package(package)
    return repository


def remote_repository(yaml_data, packages):
    repository_info = BroodRepositoryInfo("http://acme.come", "remote")
    package_names = yaml_data.get("remote", packages.keys())
    return repository_factory(package_names, repository_info, packages)


def installed_repository(yaml_data, packages):
    repository_info = BroodRepositoryInfo("http://acme.come", "installed")
    package_names = yaml_data.get("installed", [])
    return repository_factory(package_names, repository_info, packages)
