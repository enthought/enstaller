import json

from os.path import isfile, join


def meta_dir_from_prefix(prefix, package_name):
    return join(prefix, "EGG-INFO", package_name)

def info_from_metadir(meta_dir):
    path = join(meta_dir, '_info.json')
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
