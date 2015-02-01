"""
Useful code to compare solver behaviour with PHP's Composer. Obviously
don't use this in enstaller itself.
"""
import collections
import json

from enstaller.repository_info import BroodRepositoryInfo

from enstaller.new_solver.constraint_types import Any, EnpkgUpstreamMatch, Equal
from enstaller.new_solver.requirement import Requirement
from enstaller.new_solver.yaml_utils import repository_factory


def fix_php_version(version):
    """ 'Normalize' an EnpkgVersion to a valid composer version
    string.
    """
    upstream = str(version.upstream)
    while upstream.count(".") < 2:
        upstream += ".0"
    return upstream


_TO_NORMALIZE = {
    "1.0a3": "1.0.0.0-alpha3",
    "2011n": "2011.0.0.0",
    "0.14.1rc1": "0.14.1.0-RC1",
}

def normalized_php_version(version):
    """ 'Normalize' an EnpkgVersion to a valid normalized composer version
    string.
    """
    upstream = str(version.upstream)
    upstream = _TO_NORMALIZE.get(upstream, upstream)
    while upstream.count(".") < 3:
        upstream += ".0"
    return upstream


def requirement_to_php_string(requirement):
    """ Convert an enstaller requirement into a composer constraint string.
    """
    parts = []
    for constraint in requirement._constraints._constraints:
        if isinstance(constraint, EnpkgUpstreamMatch):
            normalized = normalized_php_version(constraint.version)
            parts.append("~{0}".format(normalized))
        elif isinstance(constraint, Any):
            parts.append("*")
        elif isinstance(constraint, Equal):
            normalized = normalized_php_version(constraint.version)
            parts.append("{0}".format(normalized))
        else:
            print(type(constraint))
            raise NotImplementedError(constraint)
    return ", ".join(parts)


def requirements_to_php_dict(requirements):
    """ Convert a list of requirements into a mapping
    name -> composer_requirement_string
    """
    php_dict = collections.defaultdict(list)
    for requirement in requirements:
        php_dict[requirement.name].append(requirement_to_php_string(requirement))

    return dict((k, ", ".join(v)) for k, v in php_dict.items())


def repository_to_composer_json(repository):
    res = []
    for package in repository.iter_packages():
        version_normalized = normalized_php_version(package.version)
        requires = [Requirement.from_legacy_requirement_string(p) for
                    p in package.dependencies]
        res.append({
            "name": package.name,
            "version": fix_php_version(package.version),
            "version_normalized": version_normalized,
            "require": requirements_to_php_dict(requires),
        })
    return json.dumps(res, indent=4)


def write_composer_repository(data, attribute_name, packages):
    repository_info = BroodRepositoryInfo("http://acme.come", attribute_name)
    if attribute_name == "remote":
        remote_packages = data.get(attribute_name, packages.keys())
    else:
        remote_packages = data.get(attribute_name, [])
    repository = repository_factory(remote_packages, repository_info, packages)

    filename = "{}.json".format(attribute_name)

    with open(filename, "wt") as fp:
        fp.write(repository_to_composer_json(repository))
