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
