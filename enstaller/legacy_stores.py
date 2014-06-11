from enstaller.auth import _INDEX_NAME
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


def _get_indices(config):
    if config.use_webservice:
        index_url = store_url = config.webservice_entry_point + _INDEX_NAME
        if config.use_pypi:
            index_url +=  "?pypi=true"
        else:
            index_url +=  "?pypi=false"
        return [(store_url, index_url)]
    else:
        return [(url + _INDEX_NAME, url + _INDEX_NAME)
                for url in config.IndexedRepos]


def legacy_index_parser(fetcher, config):
    """
    Yield RepositoryPackageMetadata instances from the configured stores.
    """
    for store_location, index_url in _get_indices(config):
        json_dict = _fetch_index_as_json_dict(fetcher, index_url)
        for package in _parse_index(json_dict, store_location):
            yield package
