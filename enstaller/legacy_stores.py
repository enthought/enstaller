from enstaller.repository import RepositoryPackageMetadata
from enstaller.utils import PY_VER


def parse_index(json_dict, store_location, python_version=PY_VER):
    """
    Parse the given json index data and iterate package instance over its
    content.

    Parameters
    ----------
    json_dict: dict
        Parsed legacy json index
    store_location: str
        A label describing where the index is coming from
    python_version: str
        The major.minor string describing the python version. This generator
        will iterate over every package where the python attribute is `null` or
        equal to this string. If python_version == "*", then every package is
        iterated over.
    """
    for key, info in json_dict.items():
        info.setdefault('type', 'egg')
        info.setdefault('packages', [])
        info["store_location"] = store_location
        info.setdefault('python', python_version)
        if python_version == "*":
            yield RepositoryPackageMetadata.from_json_dict(key, info)
        elif info["python"] in (None, python_version):
            yield RepositoryPackageMetadata.from_json_dict(key, info)


def _fetch_index_as_json_dict(fetcher, url):
    resp = fetcher.fetch(url)
    resp.raise_for_status()
    return resp.json()


def legacy_index_parser(fetcher, indices_and_locations, python_version=PY_VER):
    """
    Yield RepositoryPackageMetadata instances from the configured stores.

    Parameters
    ----------
    fetcher : URLFetcher
        The fetcher to use to fetch the actual index data
    indices_and_locations: list
        List of (index_url, store_location) pairs, e.g. Configuration().indices
    python_version: str
        The major.minor string describing the python version. This generator
        will iterate over every package where the python attribute is `null` or
        equal to this string. If python_version == "*", then every package is
        iterated over.
    """
    for index_url, store_location in indices_and_locations:
        json_dict = _fetch_index_as_json_dict(fetcher, index_url)
        for package in parse_index(json_dict, store_location, python_version):
            yield package
