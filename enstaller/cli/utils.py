from __future__ import absolute_import, print_function

import io
import json

from egginst._compat import urlparse

from egginst.progress import console_progress_manager_factory

from enstaller.egg_meta import split_eggname
from enstaller.fetch import URLFetcher
from enstaller.legacy_stores import parse_index
from enstaller.repository import Repository
from enstaller.requests_utils import _ResponseIterator


FMT = '%-20s %-20s %s'
VB_FMT = '%(version)s-%(build)s'
FMT4 = '%-20s %-20s %-20s %s'

DEFAULT_TEXT_WIDTH = 79


def disp_store_info(info):
    sl = info.get('store_location')
    if not sl:
        return '-'
    for rm in 'http://', 'https://', 'www', '.enthought.com', '/repo/':
        sl = sl.replace(rm, '')
    return sl.replace('/eggs/', ' ').strip('/')


def install_time_string(installed_repository, name):
    lines = []
    for info in installed_repository.find_packages(name):
        lines.append('%s was installed on: %s' % (info.key, info.ctime))
    return "\n".join(lines)


def print_installed(repository, pat=None):
    print(FMT % ('Name', 'Version', 'Store'))
    print(60 * '=')
    for package in repository.iter_packages():
        if pat and not pat.search(package.name):
            continue
        info = package._compat_dict
        print(FMT % (name_egg(package.key), VB_FMT % info,
              disp_store_info(info)))


def repository_factory(config):
    index_fetcher = URLFetcher(config.repository_cache, config.auth,
                               config.proxy_dict)
    index_fetcher._enable_etag_support()

    repository = Repository()
    for url, store_location in config.indices:
        resp = index_fetcher.fetch(url)
        resp.raise_for_status()

        for package in parse_index(_fetch_json_with_progress(resp,
                                                             store_location),
                                   store_location):
            repository.add_package(package)
    return repository


def name_egg(egg):
    return split_eggname(egg)[0]


# Private functions

def _fetch_json_with_progress(resp, store_location):
    data = io.BytesIO()

    length = int(resp.headers.get("content-length", 0))
    display = _display_store_name(store_location)
    progress = console_progress_manager_factory("Fetching index", display,
                                                size=length)
    with progress:
        for chunk in _ResponseIterator(resp):
            data.write(chunk)
            progress.update(len(chunk))

    return json.loads(data.getvalue().decode("utf-8"))


def _display_store_name(store_location):
    parts = urlparse.urlsplit(store_location)
    return urlparse.urlunsplit(("", "", parts[2], parts[3], parts[4]))
