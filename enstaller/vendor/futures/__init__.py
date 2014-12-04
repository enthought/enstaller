# Copyright 2009 Brian Quinlan. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Execute computations asynchronously using threads or processes."""
from __future__ import absolute_import

__author__ = 'Brian Quinlan (brian@sweetapp.com)'

from ._base import (FIRST_COMPLETED,
                    FIRST_EXCEPTION,
                    ALL_COMPLETED,
                    CancelledError,
                    TimeoutError,
                    Future,
                    Executor,
                    wait,
                    as_completed)
from .thread import ThreadPoolExecutor

# Jython doesn't have multiprocessing
try:
    from .process import ProcessPoolExecutor
except ImportError:
    pass
