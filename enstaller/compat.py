import urllib
import urlparse

def close_file_or_response(fp):
    if hasattr(fp, "close"):
        fp.close()
    else:
        # Compat shim for requests < 2
        fp._fp.close()

def path_to_uri(path):
    """Convert the given path to a file:// uri."""
    return urlparse.urljoin("file:", urllib.pathname2url(path))
