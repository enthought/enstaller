import os
import subprocess

from distutils.util import convert_path

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

MAJOR = 4
MINOR = 6
MICRO = 5

IS_RELEASED = True

VERSION = '%d.%d.%d' % (MAJOR, MINOR, MICRO)

# Return the git revision as a string
def git_version():
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout = subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
        git_revision = out.strip().decode('ascii')
    except OSError:
        git_revision = "Unknown"

    return git_revision

def write_version_py(filename='enstaller/_version.py'):
    template = """\
# THIS FILE IS GENERATED FROM ENSTALLER SETUP.PY
version = '{version}'
full_version = '{full_version}'
git_revision = '{git_revision}'
is_released = {is_released}

if not is_released:
    version = full_version
"""
    # Adding the git rev number needs to be done inside write_version_py(),
    # otherwise the import of numpy.version messes up the build under Python 3.
    fullversion = VERSION
    if os.path.exists('.git'):
        git_rev = git_version()
    elif os.path.exists('numpy/_version.py'):
        # must be a source distribution, use existing version file
        try:
            from enstaller._version import git_revision as git_rev
        except ImportError:
            raise ImportError("Unable to import git_revision. Try removing " \
                              "numpy/version.py and the build directory " \
                              "before building.")
    else:
        git_rev = "Unknown"

    if not IS_RELEASED:
        fullversion += '.dev1-' + git_rev[:7]

    with open(filename, "wt") as fp:
        fp.write(template.format(version=VERSION,
                                 full_version=fullversion,
                                 git_revision=git_rev,
                                 is_released=IS_RELEASED))

write_version_py()

kwds = {} # Additional keyword arguments for setup

d = {}
execfile(convert_path('enstaller/__init__.py'), d)
kwds['version'] = d['__version__']

f = open('README.rst')
kwds['long_description'] = f.read()
f.close()


setup(
    name="enstaller",
    author="Enthought, Inc.",
    author_email="info@enthought.com",
    url = "https://github.com/enthought/enstaller",
    license="BSD",
    description = "Install and managing tool for egg-based packages",
    packages = [
        'egginst',
        'egginst/macho',
        'enstaller',
        'enstaller/store',
        'enstaller/indexed_repo',
        'enstaller/proxy',
    ],
    entry_points = {
        "console_scripts": [
             "enpkg = enstaller.main:main_noexc",
             "egginst = egginst.main:main",
             "enpkg-repair = egginst.repair_broken_egg_info:main",
             "update-patches = enstaller.patch:main",
        ],
    },
    classifiers = [
        "License :: OSI Approved :: BSD License",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: System :: Software Distribution",
        "Topic :: System :: Systems Administration",
    ],
    test_suite="nose.collector",
    **kwds
)
