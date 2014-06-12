from enstaller.repository import RepositoryPackageMetadata
from enstaller.utils import PY_VER


def _parse_index(json_dict, store_location):
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


def legacy_index_parser(fetcher, config):
    """
    Yield RepositoryPackageMetadata instances from the configured stores.
    """
    for store_location, index_url in config.indices:
        json_dict = _fetch_index_as_json_dict(fetcher, index_url)
        for package in _parse_index(json_dict, store_location):
            yield package
