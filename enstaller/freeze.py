"""
Naive implementation of freeze-like feature
"""
from enstaller.repository import Repository


def get_freeze_list(prefixes):
    """
    Compute the list of eggs installed in the given prefixes.

    Returns
    -------
    names: seq
        List of installed eggs, as full names (e.g. 'numpy-1.8.0-1')
    """
    full_names = [
        "{0} {1}".format(package.name, package.full_version)
        for package in Repository._from_prefixes(prefixes).iter_packages()
    ]
    return sorted(full_names)
