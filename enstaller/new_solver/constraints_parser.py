import re

import six

from enstaller.errors import SolverException

from .constraint_types import (EnpkgUpstreamMatch, Equal, GEQ, GT,
                               LEQ, LT, Not)


_DEFAULT_SCANNER = re.Scanner([
    (r"[^=><!,\s~][^,\s]+", lambda scanner, token: VersionToken(token)),
    (r"==", lambda scanner, token: EqualToken(token)),
    (r">=", lambda scanner, token: GEQToken(token)),
    (r">", lambda scanner, token: GTToken(token)),
    (r"<=", lambda scanner, token: LEQToken(token)),
    (r"<", lambda scanner, token: LTToken(token)),
    (r"!=", lambda scanner, token: NotToken(token)),
    (r"~=", lambda scanner, token: EnpkgUpstreamMatchToken(token)),
    (",", lambda scanner, token: CommaToken(token)),
    (r"\*", lambda scanner, token: AnyToken(token)),
    (" +", lambda scanner, token: None),
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
        token = six.advance_iterator(tokens)
        try:
            while not isinstance(token, CommaToken):
                block.append(token)
                token = six.advance_iterator(tokens)
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
        self._scanner = _DEFAULT_SCANNER

    def tokenize(self, requirement_string):
        scanned, remaining = self._scanner.scan(requirement_string)
        if len(remaining) > 0:
            msg = "Invalid requirement string: {0!r}". \
                    format(requirement_string)
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
                msg = "Invalid requirement block: {0!r}". \
                        format(requirement_block)
                raise SolverException(msg)

        return constraints
