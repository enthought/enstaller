from __future__ import absolute_import

import logging

import egginst._compat


logging.getLogger("enstaller").addHandler(egginst._compat.NullHandler())

try:
    from enstaller._version import (full_version as __version__,
                                    git_revision as __git_revision__,
                                    is_released as __is_released__,
                                    )
except ImportError as e:  # pragma: no cover
    __version__ = __git_revision__ = "no-built"
    __is_released__ = False

from enstaller.config import Configuration
from enstaller.repository import Repository, RepositoryPackageMetadata
from enstaller.session import Session

__all__ = ["Configuration", "Repository", "RepositoryPackageMetadata",
           "Session"]
