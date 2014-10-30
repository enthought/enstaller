import json

from os.path import isfile, join


_INFO_FILENAME = "_info.json"


def meta_dir_from_prefix(prefix, package_name):
    return join(prefix, "EGG-INFO", package_name)


def meta_info_from_prefix(prefix, package_name):
    return join(meta_dir_from_prefix(prefix, package_name), _INFO_FILENAME)


def info_from_metadir(meta_dir):
    path = join(meta_dir, _INFO_FILENAME)
    if isfile(path):
        try:
            with open(path) as fp:
                info = json.load(fp)
        except ValueError:
            return None
        info['installed'] = True
        info['meta_dir'] = meta_dir
        return info
    return None
