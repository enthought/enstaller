"""
Naive implementation of freeze-like feature
"""
from enstaller.eggcollect import EggCollection, JoinedEggCollection

def get_freeze_list(prefixes):
    """
    Compute the list of eggs installed in the given prefixes.

    Returns
    -------
    names: seq
        List of installed eggs, as full names (e.g. 'numpy-1.8.0-1')
    """
    collection = JoinedEggCollection(
        [EggCollection(prefix, False, None) for prefix in prefixes]
    )
    full_names = [
        "{0} {1}-{2}".format(req["name"], req["version"], req["build"])
        for name, req in collection.query(type="egg")
    ]
    return sorted(full_names)
