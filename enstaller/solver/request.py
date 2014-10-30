class _Job(object):
    def __init__(self, requirement, job_type):
        self.requirement = requirement

        if job_type not in ["install", "remove", "update", "upgrade"]:
            raise ValueError("invalid job type {0}".format(job_type))
        self.kind = job_type

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
        self._add_job(requirement, "install")

    def remove(self, requirement):
        self._add_job(requirement, "remove")
