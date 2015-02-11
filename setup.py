import os
import os.path
import subprocess
import textwrap
import zipfile

from setuptools import setup

from distutils.util import convert_path

from setuptools.command.bdist_egg import bdist_egg as old_bdist_egg

from egginst.main import BOOTSTRAP_ARCNAME


MAJOR = 4
MINOR = 8
MICRO = 2

IS_RELEASED = True

VERSION = '%d.%d.%d' % (MAJOR, MINOR, MICRO)

BOOTSTRAP_SCRIPT = os.path.join(os.path.dirname(__file__), "scripts", "bootstrap.py")


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
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
        git_revision = out.strip().decode('ascii')
    except OSError:
        git_revision = "Unknown"

    try:
        out = _minimal_ext_cmd(['git', 'rev-list', '--count', 'HEAD'])
        git_count = out.strip().decode('ascii')
    except OSError:
        git_count = "0"

    return git_revision, git_count


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
    # This is only used for upgrade test. Kids, never use this by yourself !
    force_mode = os.environ.get("__TEST_FORCE_ENSTALLER_VERSION", None)
    if force_mode is not None:
        version = full_version = force_mode
        is_released = True
    else:
        version = full_version = VERSION
        is_released = IS_RELEASED

    git_rev = "Unknown"
    git_count = "0"

    if os.path.exists('.git'):
        git_rev, git_count = git_version()
    elif os.path.exists('enstaller/_version.py'):
        # must be a source distribution, use existing version file
        try:
            from enstaller._version import git_revision as git_rev
        except ImportError:
            raise ImportError("Unable to import git_revision. Try removing "
                              "enstaller/_version.py and the build directory "
                              "before building.")

    if not is_released:
        full_version += '.dev' + git_count

    with open(filename, "wt") as fp:
        fp.write(template.format(version=version,
                                 full_version=full_version,
                                 git_revision=git_rev,
                                 is_released=is_released))


class bdist_enegg(old_bdist_egg):
    def finalize_options(self):
        old_bdist_egg.finalize_options(self)

        basename = "enstaller-{0}-1.egg".format(__version__)
        self.egg_output = os.path.join(self.dist_dir, basename)

    def _write_bootstrap_code(self, bootstrap_code):
        zp = zipfile.ZipFile(self.egg_output, "a",
                             compression=zipfile.ZIP_DEFLATED)
        try:
            zp.writestr(BOOTSTRAP_ARCNAME, bootstrap_code)
        finally:
            zp.close()

    def _write_spec_depend(self, spec_depend):
        zp = zipfile.ZipFile(self.egg_output, "a",
                             compression=zipfile.ZIP_DEFLATED)
        try:
            zp.writestr("EGG-INFO/spec/depend", spec_depend)
        finally:
            zp.close()

    def run(self):
        old_bdist_egg.run(self)

        spec_depend = textwrap.dedent("""\
            metadata_version = '1.1'
            name = 'enstaller'
            version = '{0}'
            build = 1

            arch = None
            platform = None
            osdist = None
            python = None
            packages = []
        """.format(__version__))
        self._write_spec_depend(spec_depend)

        with open(BOOTSTRAP_SCRIPT, "rt") as fp:
            self._write_bootstrap_code(fp.read())


write_version_py()

kwds = {}  # Additional keyword arguments for setup

d = {}
exec(compile(open(convert_path('enstaller/__init__.py')).read(),
             convert_path('enstaller/__init__.py'),
             'exec'),
     d)
kwds['version'] = __version__ = d['__version__']

f = open('README.rst')
kwds['long_description'] = f.read()
f.close()

include_testing = True

packages = [
    'egginst',
    'egginst.console',
    'egginst.vendor',
    'enstaller',
    'enstaller.auth',
    'enstaller.cli',
    'enstaller.indexed_repo',
    'enstaller.solver',
    'enstaller.tools',
    'enstaller.vendor',
    'enstaller.vendor.cachecontrol',
    'enstaller.vendor.cachecontrol.caches',
    'enstaller.vendor.futures',
    'enstaller.vendor.jsonschema',
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
    'enstaller.vendor.yaml_py3',
    'enstaller.versions',
]

package_data = {"enstaller.vendor.requests": ["cacert.pem"],
                "enstaller.vendor.jsonschema": ["schemas/draft3.json", "schemas/draft4.json"]}

if include_testing:
    packages += [
        'egginst.tests',
        'enstaller.auth.tests',
        'enstaller.cli.tests',
        'enstaller.indexed_repo.tests',
        'enstaller.solver.tests',
        'enstaller.tests',
        'enstaller.tools.tests',
        'enstaller.versions.tests',
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
    url="https://github.com/enthought/enstaller",
    license="BSD",
    description="Install and managing tool for egg-based packages",
    packages=packages,
    package_data=package_data,
    entry_points={
        "console_scripts": [
            "enpkg = enstaller.main:main_noexc",
            "egginst = egginst.main:main",
            "enpkg-repair = egginst.repair_broken_egg_info:main",
            "update-patches = enstaller.patch:main",
        ],
    },
    classifiers=[
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
    cmdclass={"bdist_enegg": bdist_enegg},
    **kwds
)
