from enstaller.repository import RepositoryPackageMetadata
from enstaller.utils import PY_VER


def parse_index(json_dict, store_location):
    for key, info in json_dict.items():
        info.setdefault('type', 'egg')
        info.setdefault('python', PY_VER)
        info.setdefault('packages', [])
        info["store_location"] = store_location
        yield RepositoryPackageMetadata.from_json_dict(key, info)


def _fetch_index_as_json_dict(fetcher, url):
    resp = fetcher.fetch(url)
    resp.raise_for_status()
    return resp.json()


def legacy_index_parser(fetcher, indices_and_locations):
    """
    Yield RepositoryPackageMetadata instances from the configured stores.

    Parameters
    ----------
    fetcher : URLFetcher
        The fetcher to use to fetch the actual index data
    indices_and_locations: list
        List of (index_url, store_location) pairs, e.g. Configuration().indices
    """
    for index_url, store_location in indices_and_locations:
        json_dict = _fetch_index_as_json_dict(fetcher, index_url)
        for package in parse_index(json_dict, store_location):
            yield package
