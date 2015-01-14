import re

from enstaller.new_solver.constraints_parser import _RawRequirementParser


DEPENDS_RE = re.compile("depends\s*\((.*)\)")


class PrettyPackageStringParser(object):
    """ Parser for pretty package strings.

    Pretty package strings are of the form::

        numpy 1.8.1-1; depends (MKL == 10.3, nose ~= 1.3.4)
    """
    def __init__(self, version_factory):
        self._parser = _RawRequirementParser()
        self._version_factory = version_factory

    def parse(self, package_string):
        """ Parse the given pretty package string.

        Parameters
        ----------
        package_string : str
            The pretty package string, e.g.
            "numpy 1.8.1-1; depends (MKL == 10.3, nose ~= 1.3.4)"

        Returns
        -------
        name : str
            The package name
        version : version object
            The package version
        dependencies : dict
            A dict mapping a package name to a set of constraints mapping.
        """
        version_factory = self._version_factory

        parts = package_string.split(";")

        name, version_string = _parse_preambule(parts[0])

        constraints = {}

        for part in parts[1:]:
            part = part.lstrip()

            m = None
            for kind, r in (("dependencies", DEPENDS_RE),):
                m = r.search(part)
                if m:
                    constraints[kind] = m.group(1)

            if m is None:
                msg = "Invalid constraint block: '{0}'".format(part)
                raise ValueError(msg)

            constraints[kind] = dict(self._parser.parse(m.group(1), version_factory))

        return (name, version_factory(version_string),
                constraints.get("dependencies", {}))


def _parse_preambule(preambule):
    parts = preambule.strip().split()
    if not len(parts) == 2:
        raise ValueError("Invalid preambule: {0!r}".format(preambule))
    else:
        return parts[0], parts[1]
