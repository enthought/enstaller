import collections
import re

from enstaller.errors import SolverException

from .constraint_types import (EnpkgUpstreamMatch, Equal, GEQ, GT,
                               LEQ, LT, Not)


_VERSION_R = "[^=><!,\s~][^,\s]+"
_EQUAL_R = "=="
_GEQ_R = ">="
_GT_R = r">"
_LEQ_R = r"<="
_LT_R = r"<"
_NOT_R = r"!="
_ENPKG_UPSTREAM_MATCH_R = r"~="
_COMMA_R = ","
_ANY_R = r"\*"
_WS_R = " +"

_CONSTRAINTS_SCANNER = re.Scanner([
    (_VERSION_R, lambda scanner, token: VersionToken(token)),
    (_EQUAL_R, lambda scanner, token: EqualToken(token)),
    (_GEQ_R, lambda scanner, token: GEQToken(token)),
    (_GT_R, lambda scanner, token: GTToken(token)),
    (_LEQ_R, lambda scanner, token: LEQToken(token)),
    (_LT_R, lambda scanner, token: LTToken(token)),
    (_NOT_R, lambda scanner, token: NotToken(token)),
    (_ENPKG_UPSTREAM_MATCH_R,
        lambda scanner, token: EnpkgUpstreamMatchToken(token)),
    (_COMMA_R, lambda scanner, token: CommaToken(token)),
    (_ANY_R, lambda scanner, token: AnyToken(token)),
    (_WS_R, lambda scanner, token: None),
])

_DISTRIBUTION_R = "[a-zA-Z_]\w*"

_REQUIREMENTS_SCANNER = re.Scanner([
    (_DISTRIBUTION_R, lambda scanner, token: DistributionNameToken(token)),
    (_VERSION_R, lambda scanner, token: VersionToken(token)),
    (_EQUAL_R, lambda scanner, token: EqualToken(token)),
    (_GEQ_R, lambda scanner, token: GEQToken(token)),
    (_GT_R, lambda scanner, token: GTToken(token)),
    (_LEQ_R, lambda scanner, token: LEQToken(token)),
    (_LT_R, lambda scanner, token: LTToken(token)),
    (_NOT_R, lambda scanner, token: NotToken(token)),
    (_ENPKG_UPSTREAM_MATCH_R,
        lambda scanner, token: EnpkgUpstreamMatchToken(token)),
    (_COMMA_R, lambda scanner, token: CommaToken(token)),
    (_ANY_R, lambda scanner, token: AnyToken(token)),
    (_WS_R, lambda scanner, token: None),
])


class Token(object):
    kind = None

    def __init__(self, value=None):
        self.value = value


class CommaToken(Token):
    kind = "comma"


class DistributionNameToken(Token):
    kind = "distribution_name"


class AnyToken(Token):
    kind = "any"


class VersionToken(Token):
    kind = "version"


class ComparisonToken(Token):
    kind = "comparison"


class LEQToken(ComparisonToken):
    kind = "leq"


class LTToken(ComparisonToken):
    kind = "lt"


class GEQToken(ComparisonToken):
    kind = "geq"


class GTToken(ComparisonToken):
    kind = "gt"


class EnpkgUpstreamMatchToken(ComparisonToken):
    kind = "enpkg_upstream"


class EqualToken(ComparisonToken):
    kind = "equal"


class NotToken(ComparisonToken):
    kind = "not"


def iter_over_requirement(tokens):
    """Yield a single requirement 'block' (i.e. a sequence of tokens between
    comma).

    Parameters
    ----------
    tokens: iterator
        Iterator of tokens
    """
    while True:
        block = []
        token = next(tokens)
        try:
            while not isinstance(token, CommaToken):
                block.append(token)
                token = next(tokens)
            yield block
        except StopIteration as e:
            yield block
            raise e


_OPERATOR_TO_SPEC = {
    EnpkgUpstreamMatchToken: EnpkgUpstreamMatch,
    EqualToken: Equal,
    GEQToken: GEQ,
    GTToken: GT,
    LEQToken: LEQ,
    LTToken: LT,
    NotToken: Not,
}


def _spec_factory(comparison_token):
    klass = _OPERATOR_TO_SPEC.get(comparison_token.__class__, None)
    if klass is None:
        msg = "Unsupported comparison token {0!r}".format(comparison_token)
        raise SolverException(msg)
    else:
        return klass


class _RawConstraintsParser(object):
    """A simple parser for requirement strings."""
    def __init__(self):
        self._scanner = _CONSTRAINTS_SCANNER

    def tokenize(self, requirement_string):
        scanned, remaining = self._scanner.scan(requirement_string)
        if len(remaining) > 0:
            msg = ("Invalid requirement string: {0!r}".
                   format(requirement_string))
            raise SolverException(msg)
        else:
            return iter(scanned)

    def parse(self, requirement_string, version_factory):
        constraints = set()

        tokens_stream = self.tokenize(requirement_string)
        for requirement_block in iter_over_requirement(tokens_stream):
            if len(requirement_block) == 2:
                operator, version = requirement_block
                operator = _spec_factory(operator)
                version = version_factory(version.value)
                constraints.add(operator(version))
            else:
                msg = ("Invalid requirement block: {0!r}".
                       format(requirement_block))
                raise SolverException(msg)

        return constraints


class _RawRequirementParser(object):
    """A simple parser for requirement strings."""
    def __init__(self):
        self._scanner = _REQUIREMENTS_SCANNER

    def tokenize(self, requirement_string):
        scanned, remaining = self._scanner.scan(requirement_string)
        if len(remaining) > 0:
            msg = ("Invalid requirement string: {0!r}".
                   format(requirement_string))
            raise SolverException(msg)
        else:
            return iter(scanned)

    def parse(self, requirement_string, version_factory):
        constraints = collections.defaultdict(set)

        tokens_stream = self.tokenize(requirement_string)
        for requirement_block in iter_over_requirement(tokens_stream):
            if len(requirement_block) == 3:
                distribution, operator, version = requirement_block
                name = distribution.value
                operator = _spec_factory(operator)
                version = version_factory(version.value)
                constraints[name].add(operator(version))
            else:
                msg = ("Invalid requirement block: {0!r}".
                       format(requirement_block))
                raise SolverException(msg)

        return constraints
