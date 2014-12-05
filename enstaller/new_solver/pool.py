import collections


class Pool(object):
    """ A pool of repositories.

    The main feature of a pool is to search for every package matching a
    given requirement.
    """
    def __init__(self, repositories=None):
        self._packages_by_id = {}
        self._packages_by_name = collections.defaultdict(list)
        self._repositories = []

        self._id = 1

        repositories = repositories or []
        for repository in repositories:
            self.add_repository(repository)

    def add_repository(self, repository):
        """ Add the repository to this pool.

        Parameters
        ----------
        repository : Repository
            The repository to add
        """
        for package in repository.iter_packages():
            package.id = self._id
            self._id += 1

            self._packages_by_id[package.id] = package

            self._packages_by_name[package.name].append(package)

    def what_provides(self, requirement):
        """ Computes the list of packages fulfilling the given
        requirement.

        Parameters
        ----------
        requirement : Requirement
            The requirement to match candidates against.
        """
        ret = []
        if requirement.name in self._packages_by_name:
            for package in self._packages_by_name[requirement.name]:
                if requirement.matches(package.version):
                    ret.append(package)
        return ret

    def id_to_string(self, package_id):
        """
        Convert a package id to a nice string representation.
        """
        package = self._packages_by_id[abs(package_id)]
        package_string = package.name + "-" + package.full_version
        if package_id > 0:
            return "+" + package_string
        else:
            return "-" + package_string
