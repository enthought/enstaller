from __future__ import print_function

import sys

import json
import time

from os.path import join

from egginst._zipfile import ZipFile
from egginst.utils import parse_assignments
from egginst.vendor.six.moves import StringIO


# Path relative to EGG-INFO in egg, or $RPPT/EGG-INFO/$package_name when
# installed
APPINST_PATH = join("inst", "appinst.dat")

SPEC_DEPEND_KEYS = ('name', 'version', 'build', 'arch', 'platform', 'osdist',
                    'python', 'packages')


def parse_rawspec(data):
    # XXX: hack to workaround 2.6-specific bug with ast-parser and
    # unicode.
    if sys.version_info < (2, 7, 3):
        spec = parse_assignments(StringIO(data.encode("utf8")))
    else:
        spec = parse_assignments(StringIO(data))
    res = {}
    for k in SPEC_DEPEND_KEYS:
        res[k] = spec[k]
    return res


def info_from_z(z):
    res = dict(type='egg')

    arcname = 'EGG-INFO/spec/depend'
    if arcname in z.namelist():
        res.update(parse_rawspec(z.read(arcname).decode("utf8")))

    arcname = 'EGG-INFO/info.json'
    if arcname in z.namelist():
        res.update(json.loads(z.read(arcname).decode("utf8")))

    res['name'] = res['name'].lower().replace('-', '_')
    return res


def create_info(egg, extra_info=None):
    info = dict(key=egg.fn)
    info.update(info_from_z(egg.z))
    info['ctime'] = time.ctime()
    # FIXME: hook kept for compat for now.
    info['hook'] = False
    if extra_info:
        info.update(extra_info)

    try:
        del info['available']
    except KeyError:
        pass

    with open(join(egg.meta_dir, '_info.json'), 'w') as fo:
        json.dump(info, fo, indent=2, sort_keys=True)

    return info


def is_custom_egg(egg):
    """
    Return True if the egg is built using Enthought build infrastructure, False
    otherwise.

    Note
    ----
    This is not 100 % reliable, as some Enthought eggs don't always have any
    specific metadata.
    """
    with ZipFile(egg) as zp:
        for dest in ("spec/depend", "inst/targets.dat"):
            try:
                zp.getinfo("EGG-INFO/{0}".format(dest))
                return True
            except KeyError:
                pass
        return False
