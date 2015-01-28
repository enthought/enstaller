"""
Useful code to compare solver behaviour with PHP's Composer. Obviously
don't use this in enstaller itself.
"""
import collections
import json

from enstaller.new_solver.constraint_types import Any, EnpkgUpstreamMatch, Equal
from enstaller.new_solver.requirement import Requirement


def normalized_php_version(version):
    """ 'Normalize' an EnpkgVersion to a valid normalized composer version
    string.
    """
    upstream = str(version.upstream)
    if upstream.count(".") < 3:
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
            parts.append("=={0}".format(normalized))
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
            "version": str(package.version.upstream),
            "version_normalized": version_normalized,
            "require": requirements_to_php_dict(requires),
        })
    return json.dumps(res, indent=4)


if __name__ == "__main__":
    from enstaller.new_solver.tests.common import repository_from_index

    repository = repository_from_index("index.json")
    with open("remote.json", "wt") as fp:
        fp.write(repository_to_composer_json(repository))
