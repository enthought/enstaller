from __future__ import absolute_import

from egginst._compat import pathname2url, urljoin


def close_file_or_response(fp):
    if hasattr(fp, "close"):
        fp.close()
    else:
        # Compat shim for requests < 2
        fp._fp.close()


def path_to_uri(path):
    """Convert the given path to a file:// uri."""
    return urljoin("file:", pathname2url(path))


try:
    from collections import OrderedDict
except ImportError:
    from .ordered_dict import OrderedDict


__all__ = ["OrderedDict", "close_file_or_response", "path_to_uri"]
