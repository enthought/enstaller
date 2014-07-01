# Changes library path in object code (ELF and Mach-O).
from __future__ import print_function

import logging
import sys
import re
from os.path import abspath, join, islink, isfile, exists


logger = logging.getLogger(__name__)

# extensions which are assumed to belong to files which don't contain
# object code
NO_OBJ = ('.py', '.pyc', '.pyo', '.h', '.a', '.c', '.txt', '.html', '.xml',
          '.png', '.jpg', '.gif')

MAGIC = {
    '\xca\xfe\xba\xbe': 'MachO-universal',
    '\xce\xfa\xed\xfe': 'MachO-i386',
    '\xcf\xfa\xed\xfe': 'MachO-x86_64',
    '\xfe\xed\xfa\xce': 'MachO-ppc',
    '\xfe\xed\xfa\xcf': 'MachO-ppc64',
    '\x7fELF': 'ELF',
}

# list of target direcories where shared object files are found
_targets = []


def get_object_type(path):
    """
    Return the object file type of the specified file (not link).
    Otherwise, if the file is not an object file, returns None.
    """
    if path.endswith(NO_OBJ) or islink(path) or not isfile(path):
        return None
    with open(path, 'rb') as fi:
        head = fi.read(4)
    return MAGIC.get(head)


def find_lib(fn):
    for tgt in _targets:
        dst = abspath(join(tgt, fn))
        if exists(dst):
            return dst
    logger.error("ERROR: library %r not found", fn)
    return join('/ERROR/path/not/found', fn)


placehold_pat = re.compile(5 * '/PLACEHOLD' + '([^\0\\s]*)\0')
def fix_object_code(path):
    tp = get_object_type(path)
    if tp is None:
        return

    with open(path, 'r+b') as f:
        data = f.read()
        matches = list(placehold_pat.finditer(data))
        if not matches:
            return

        logger.info("Fixing placeholders in: %r", path)
        for m in matches:
            rest = m.group(1)
            original_r = rest
            while rest.startswith('/PLACEHOLD'):
                rest = rest[10:]

            if tp.startswith('MachO-') and rest.startswith('/'):
                # If the /PLACEHOLD is found in a LC_LOAD_DYLIB command
                r = find_lib(rest[1:])
            else:
                # If the /PLACEHOLD is found in a LC_RPATH command (Mach-O) or in
                # R(UN)PATH on ELF
                assert rest == '' or rest.startswith(':')
                rpaths = list(_targets)
                # extend the list with rpath which were already in the binary,
                # if any
                rpaths.extend(p for p in rest.split(':') if p)
                r = ':'.join(rpaths)

            logger.info("replacing rpath %r with %r", original_r, r)

            padding = len(m.group(0)) - len(r)
            if padding < 1: # we need at least one null-character
                raise Exception("placeholder %r too short" % m.group(0))
            r += padding * '\0'
            assert m.start() + len(r) == m.end()
            f.seek(m.start())
            f.write(r)


def _compute_targets(egg):
    prefixes = [egg.prefix] if egg.prefix != abspath(sys.prefix) else [sys.prefix]

    targets = []
    for prefix in prefixes:
        for line in egg.iter_targets():
            targets.append(join(prefix, line))
        targets.append(join(prefix, 'lib'))

    logger.info('Target directories:')
    for tgt in targets:
        logger.info('    %r', tgt)

    return targets


def fix_files(egg):
    """
    Tries to fix the library path for all object files installed by the egg.
    """
    global _targets

    _targets = _compute_targets(egg)

    for p in egg.files:
        fix_object_code(p)
