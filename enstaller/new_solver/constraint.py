from .constraint_types import (Any, EnpkgUpstreamMatch, Equal, GEQ, GT,
                               LEQ, LT, Not)


def are_compatible(left_constraint, candidate_version):
    return left_constraint.matches(candidate_version)
