from enum import Enum


class JobType(Enum):
    install = 1
    remove = 2
    update = 3


class _Job(object):
    def __init__(self, requirement, kind):
        self.requirement = requirement
        try:
            self.kind = JobType(kind)
        except ValueError:
            raise ValueError("Invalid job type: {0!r}".format(kind))

    def __eq__(self, other):
        if other is None:
            return False
        else:
            return self.kind == other.kind \
                and self.requirement == other.requirement


class Request(object):
    def __init__(self):
        self.jobs = []

    def _add_job(self, requirement, job_type):
        self.jobs.append(_Job(requirement, job_type))

    def install(self, requirement):
        self._add_job(requirement, JobType.install)

    def remove(self, requirement):
        self._add_job(requirement, JobType.remove)

    def update(self, requirement):
        self._add_job(requirement, JobType.update)
