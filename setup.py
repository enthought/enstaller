import os
import subprocess

from setuptools import setup
from distutils.util import convert_path

MAJOR = 4
MINOR = 7
MICRO = 6

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

include_testing = True

packages = [
    'egginst',
    'egginst.console',
    'egginst.macho',
    'enstaller',
    'enstaller.indexed_repo',
    'enstaller.vendor',
    'enstaller.vendor.cachecontrol',
    'enstaller.vendor.cachecontrol.caches',
    'enstaller.vendor.keyring',
    'enstaller.vendor.keyring.backends',
    'enstaller.vendor.keyring.util',
    'enstaller.vendor.requests',
    'enstaller.vendor.requests.packages',
    'enstaller.vendor.requests.packages.chardet',
    'enstaller.vendor.requests.packages.urllib3',
    'enstaller.vendor.requests.packages.urllib3.contrib',
    'enstaller.vendor.requests.packages.urllib3.packages',
    'enstaller.vendor.requests.packages.urllib3.packages.ssl_match_hostname',
    'enstaller.vendor.requests.packages.urllib3.util',
    'enstaller.vendor.sqlite_cache',
    'enstaller.vendor.win32ctypes',
    'enstaller.vendor.yaml',
]

package_data = {"enstaller.vendor.requests": ["cacert.pem"]}

if include_testing:
    packages += [
        'egginst.tests',
        'enstaller.indexed_repo.tests',
        'enstaller.tests',
    ]
    macho_binaries = """dummy_with_target_dat-1.0.0-1.egg  foo_amd64
    foo_legacy_placehold.dylib  foo_rpath.dylib  foo.so  foo_x86
    libfoo.dylib""".split()

    package_data["egginst.tests"] = ["data/*egg", "data/zip_with_softlink.zip"]
    package_data["egginst.tests"] += [os.path.join("data", "macho", p)
                                      for p in macho_binaries]

    package_data["enstaller.indexed_repo.tests"] = [
        "*.txt",
        "epd/*.txt", "gpl/*.txt",
        "open/*.txt",
        "runner/*.txt",
    ]

setup(
    name="enstaller",
    author="Enthought, Inc.",
    author_email="info@enthought.com",
    url = "https://github.com/enthought/enstaller",
    license="BSD",
    description = "Install and managing tool for egg-based packages",
    packages = packages,
    package_data=package_data,
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
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: System :: Software Distribution",
        "Topic :: System :: Systems Administration",
    ],
    test_suite="nose.collector",
    **kwds
)
