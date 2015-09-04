import ast
import os
import os.path
import subprocess
import textwrap
import zipfile

from setuptools import setup

from setuptools.command.bdist_egg import bdist_egg as old_bdist_egg


MAJOR = 4
MINOR = 9
MICRO = 0

IS_RELEASED = False

VERSION = '%d.%d.%d' % (MAJOR, MINOR, MICRO)

BOOTSTRAP_SCRIPT = os.path.join(os.path.dirname(__file__), "egginst", "bootstrap.py")

INSTALL_REQUIRES = [
    "cachecontrol>=0.11.5",
    "enum34",
    "jsonschema",
    "okonomiyaki >= 0.10.0",
    "requests>=2.7.0",
    "ruamel.yaml>=0.10.7",
    "sqlite_cache>=0.0.3",
    "zipfile2 >= 0.0.10",
]

EXTRAS_REQUIRE = {
    ':python_version<="3.0"': ['futures',]
}

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
version = '{final_version}'
full_version = '{full_version}'
git_revision = '{git_revision}'
is_released = {is_released}
"""
    force_mode = os.environ.get("FORCE_ENSTALLER_VERSION", None)
    if force_mode is not None:
        assert not IS_RELEASED, \
            "FORCE_ENSTALLER_VERSION mode in release mode !"
        version = full_version = force_mode
        is_released = True
    else:
        version = full_version = VERSION
        is_released = IS_RELEASED

    git_rev = "Unknown"
    git_count = "0"

    if os.path.exists('.git'):
        git_rev, git_count = git_version()
    elif os.path.exists(filename):
        return

    if not is_released:
        full_version += '.dev' + git_count
        final_version = full_version
    else:
        final_version = version

    with open(filename, "wt") as fp:
        fp.write(template.format(final_version=final_version,
                                 full_version=full_version,
                                 git_revision=git_rev,
                                 is_released=is_released))


class _AssignmentParser(ast.NodeVisitor):
    def __init__(self):
        self._data = {}

    def parse(self, s):
        self._data.clear()

        root = ast.parse(s)
        self.visit(root)
        return self._data

    def generic_visit(self, node):
        if type(node) != ast.Module:
            raise ValueError("Unexpected expression @ line {0}".
                             format(node.lineno), node.lineno)
        super(_AssignmentParser, self).generic_visit(node)

    def visit_Assign(self, node):
        value = ast.literal_eval(node.value)
        for target in node.targets:
            self._data[target.id] = value


def parse_version(path):
    with open(path) as fp:
        return _AssignmentParser().parse(fp.read())["version"]


class bdist_enegg(old_bdist_egg):
    def finalize_options(self):
        old_bdist_egg.finalize_options(self)

        basename = "enstaller-{0}-1.egg".format(__version__)
        self.egg_output = os.path.join(self.dist_dir, basename)

    def _write_bootstrap_code(self, bootstrap_code):
        from egginst.main import BOOTSTRAP_ARCNAME
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
_version_file = os.path.join("enstaller", "_version.py")

kwds = {}  # Additional keyword arguments for setup

kwds['version'] = __version__ = parse_version(_version_file)

with open('README.rst') as fp:
    kwds['long_description'] = fp.read()

include_testing = True

packages = [
    'egginst',
    'egginst.console',
    'enstaller',
    'enstaller.auth',
    'enstaller.cli',
    'enstaller.compat',
    'enstaller.new_solver',
    'enstaller.solver',
    'enstaller.tools',
    'enstaller.versions',
]

package_data = {}

if include_testing:
    packages += [
        'egginst.tests',
        'enstaller.auth.tests',
        'enstaller.cli.tests',
        'enstaller.new_solver.tests',
        'enstaller.solver.tests',
        'enstaller.tests',
        'enstaller.tools.tests',
        'enstaller.versions.tests',
    ]
    macho_binaries = """dummy_with_target_dat-1.0.0-1.egg  foo_amd64
    foo_legacy_placehold.dylib  foo_rpath.dylib  foo.so  foo_x86
    libfoo.dylib foo_legacy_placehold_lc_rpath.dylib""".split()

    package_data["egginst.tests"] = ["data/*egg", "data/zip_with_softlink.zip"]
    package_data["egginst.tests"] += [os.path.join("data", "macho", p)
                                      for p in macho_binaries]

    package_data["enstaller.indexed_repo.tests"] = [
        "*.txt",
        "epd/*.txt", "gpl/*.txt",
        "open/*.txt",
        "runner/*.txt",
    ]

    package_data["enstaller.new_solver.tests"] = [
        "data/*.json",
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
    extras_require=EXTRAS_REQUIRE,
    install_requires=INSTALL_REQUIRES,
    **kwds
)
