from egginst._compat import PY2
from egginst.vendor import six
if PY2:
    from enstaller.vendor import yaml
else:
    from enstaller.vendor import yaml_py3 as yaml

from enstaller.compat import OrderedDict
from enstaller.package import RepositoryPackageMetadata
from enstaller.repository import Repository
from enstaller.repository_info import BroodRepositoryInfo
from enstaller.solver import Request
from enstaller.utils import PY_VER
from enstaller.versions.enpkg import EnpkgVersion

from .package_parser import PrettyPackageStringParser
from .requirement import Requirement


def parse_package_list(packages):
    """ Yield PackageMetadata instances given an sequence  of pretty package
    strings.

    Parameters
    ----------
    packages : iterator
        An iterator of package strings (e.g.
        'numpy 1.8.1-1; depends (MKL ~= 10.3)').
    """
    parser = PrettyPackageStringParser(EnpkgVersion.from_string)

    for package_str in packages:
        package = parser.parse_to_package(package_str, PY_VER)
        full_name = "{0} {1}".format(package.name, package.full_version)
        yield full_name, package


def repository_factory(package_names, repository_info, reference_packages):
    repository = Repository()
    for package_name in package_names:
        package = reference_packages[package_name]
        package = RepositoryPackageMetadata.from_package(package, repository_info)
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


class Scenario(object):
    @classmethod
    def from_yaml(cls, file_or_filename):
        if isinstance(file_or_filename, six.string_types):
            with open(file_or_filename) as fp:
                data = yaml.load(fp)
        else:
            data = yaml.load(file_or_filename)

        packages = OrderedDict(
            parse_package_list(data.get("packages", []))
        )
        operations = data.get("request", [])

        request = Request()

        for operation in operations:
            kind = operation["operation"]
            requirement = Requirement._from_string(operation["requirement"])
            getattr(request, kind)(requirement)

        decisions = data.get("solution", {})
        return cls(packages, [remote_repository(data, packages)],
                   installed_repository(data, packages), request,
                   decisions)

    def __init__(self, packages, remote_repositories, installed_repository,
                 request, decisions):
        self.packages = packages
        self.remote_repositories = remote_repositories
        self.installed_repository = installed_repository
        self.request = request
        self.decisions = decisions

    def print_solution(self, pool, positive_decisions):
        for package_id in sorted(positive_decisions):
            package = pool._id_to_package[package_id]
            print("{}: {} {}".format(package_id, package.name,
                                     package.full_version))
