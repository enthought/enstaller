from egginst.vendor.six.moves import urllib


def close_file_or_response(fp):
    if hasattr(fp, "close"):
        fp.close()
    else:
        # Compat shim for requests < 2
        fp._fp.close()


def path_to_uri(path):
    """Convert the given path to a file:// uri."""
    return urllib.parse.urljoin("file:", urllib.request.pathname2url(path))
