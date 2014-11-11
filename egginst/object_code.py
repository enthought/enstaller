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
    b'\xca\xfe\xba\xbe': 'MachO-universal',
    b'\xce\xfa\xed\xfe': 'MachO-i386',
    b'\xcf\xfa\xed\xfe': 'MachO-x86_64',
    b'\xfe\xed\xfa\xce': 'MachO-ppc',
    b'\xfe\xed\xfa\xcf': 'MachO-ppc64',
    b'\x7fELF': 'ELF',
}

PLACEHOLD_PAT = re.compile(5 * b'/PLACEHOLD' + b'([^\0\\s]*)\0')


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


def _find_lib(fn, targets):
    for tgt in targets:
        dst = abspath(join(tgt, fn))
        if exists(dst):
            return dst
    logger.error("ERROR: library %r not found", fn)
    return join('/ERROR/path/not/found', fn)


def _fix_object_code(path, targets):
    tp = get_object_type(path)
    if tp is None:
        return

    with open(path, 'r+b') as f:
        data = f.read()
        matches = list(PLACEHOLD_PAT.finditer(data))
        if not matches:
            return

        logger.info("Fixing placeholders in: %r", path)
        for m in matches:
            rest = m.group(1)
            original_r = rest
            while rest.startswith(b'/PLACEHOLD'):
                rest = rest[10:]

            if tp.startswith('MachO-') and rest.startswith(b'/'):
                # If the /PLACEHOLD is found in a LC_LOAD_DYLIB command
                r = _find_lib(rest[1:].decode("utf8"), targets).encode("utf8")
            else:
                # If the /PLACEHOLD is found in a LC_RPATH command (Mach-O) or in
                # R(UN)PATH on ELF
                assert rest == b'' or rest.startswith(b':')
                rpaths = list(target.encode("utf8") for target in targets)
                # extend the list with rpath which were already in the binary,
                # if any
                rpaths.extend(p for p in rest.split(b':') if p)
                r = b':'.join(rpaths)

            logger.info("replacing rpath %r with %r", original_r, r)

            padding = len(m.group(0)) - len(r)
            if padding < 1:  # we need at least one null-character
                raise Exception("placeholder %r too short" % m.group(0))
            r += padding * b'\0'
            assert m.start() + len(r) == m.end()
            f.seek(m.start())
            f.write(r)


def _compute_targets(egg_targets, prefix):
    """
    Compute the list of target direcories where shared object files are found
    """
    prefixes = [prefix] if prefix != abspath(sys.prefix) else [sys.prefix]

    targets = []
    for prefix in prefixes:
        for target in egg_targets:
            targets.append(join(prefix, target))
        targets.append(join(prefix, 'lib'))

    logger.info('Target directories:')
    for tgt in targets:
        logger.info('    %r', tgt)

    return targets


def apply_placeholder_hack(files, egg_targets, prefix):
    """
    Tries to fix the library path for all object files installed by the egg.
    """
    targets = _compute_targets(egg_targets, prefix)

    for path in files:
        _fix_object_code(path, targets)


# XXX: kept for legacy reason, DO NOT REMOVE.
# This code is used during enstaller inplace update.
def fix_files(egg_inst):
    if egg_inst.cname != "enstaller":
        msg = "Legacy dummy code used for an egg not called enstaller !"
        raise RuntimeError(msg)
