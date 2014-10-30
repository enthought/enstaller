from egginst._compat import urlparse
from egginst._compat import pathname2url


def close_file_or_response(fp):
    if hasattr(fp, "close"):
        fp.close()
    else:
        # Compat shim for requests < 2
        fp._fp.close()


def path_to_uri(path):
    """Convert the given path to a file:// uri."""
    return urlparse.urljoin("file:", pathname2url(path))
