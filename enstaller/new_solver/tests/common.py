import json
import os.path

from enstaller import Repository
from enstaller.legacy_stores import parse_index


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "data")


def repository_from_index(path):
    repository = Repository()
    with open(path) as fp:
        data = json.load(fp)
    for package in parse_index(data, "", "2.7"):
        repository.add_package(package)
    return repository
