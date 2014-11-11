import contextlib
import os
import shutil
import subprocess
import sys
import tempfile

SUPPORT_SYMLINK = hasattr(os, "symlink")

MACHO_DIRECTORY = os.path.join(os.path.dirname(__file__), "data", "macho")

LEGACY_PLACEHOLD_FILE_RPATH = os.path.join(MACHO_DIRECTORY,
                                           "foo_legacy_placehold_lc_rpath.dylib")
LEGACY_PLACEHOLD_FILE_LOAD_DYLIB = os.path.join(MACHO_DIRECTORY,
                                                "foo_legacy_placehold_lc_dylib.dylib")
NOLEGACY_RPATH_FILE = os.path.join(MACHO_DIRECTORY, "foo_rpath.dylib")

PYEXT_WITH_LEGACY_PLACEHOLD_DEPENDENCY = os.path.join(MACHO_DIRECTORY, "foo.so")
PYEXT_DEPENDENCY = os.path.join(MACHO_DIRECTORY, "libfoo.dylib")

FILE_TO_RPATHS = {
    NOLEGACY_RPATH_FILE: ["@loader_path/../lib"],
    LEGACY_PLACEHOLD_FILE_RPATH: ["/PLACEHOLD" * 20],
}

MACHO_ARCH_TO_FILE = {
    "x86": os.path.join(MACHO_DIRECTORY, "foo_x86"),
    "amd64": os.path.join(MACHO_DIRECTORY, "foo_amd64"),
}

PYTHON_VERSION = ".".join(str(i) for i in sys.version_info[:2])

DUMMY_EGG_WITH_INST_TARGETS = os.path.join(MACHO_DIRECTORY, "dummy_with_target_dat-1.0.0-1.egg")

_EGGINST_COMMON_DATA = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")
DUMMY_EGG_WITH_APPINST = os.path.join(_EGGINST_COMMON_DATA, "dummy_with_appinst-1.0.0-1.egg")

DUMMY_EGG = os.path.join(_EGGINST_COMMON_DATA, "dummy-1.0.1-1.egg")
DUMMY_EGG_METADATA_FILES = ("PKG-INFO", "spec/depend", "spec/summary")

DUMMY_EGG_WITH_ENTRY_POINTS = os.path.join(_EGGINST_COMMON_DATA, "dummy_with_entry_points-1.0.0-1.egg")
DUMMY_WITH_PROXY_EGG = os.path.join(_EGGINST_COMMON_DATA, "dummy_with_proxy-1.3.40-3.egg")

__st = os.stat(DUMMY_EGG)
DUMMY_EGG_MTIME = __st.st_mtime
DUMMY_EGG_SIZE = __st.st_size
DUMMY_EGG_MD5 = "1ec1f69526c55db7420b0d480c9b955e"

NOSE_1_2_1 = os.path.join(os.path.dirname(__file__), "data", "nose-1.2.1-1.egg")
NOSE_1_3_0 = os.path.join(os.path.dirname(__file__), "data", "nose-1.3.0-1.egg")

STANDARD_EGG = os.path.join(_EGGINST_COMMON_DATA, "Jinja2-2.6-py2.7.egg")
STANDARD_EGG_METADATA_FILES = (
    "dependency_links.txt", "entry_points.txt", "not-zip-safe", "PKG-INFO",
    "requires.txt", "SOURCES.txt", "top_level.txt"
)

STANDARD_EGG_WITH_EXT = os.path.join(_EGGINST_COMMON_DATA, "PyYAML-3.11-py2.7-linux-x86_64.egg")

LEGACY_EGG_INFO_EGG = os.path.join(_EGGINST_COMMON_DATA, "flake8-2.0.0-2.egg")
LEGACY_EGG_INFO_EGG_METADATA_FILES = (
    "PKG-INFO", "requires.txt", "SOURCES.txt", "dependency_links.txt",
    "top_level.txt", "entry_points.txt"
)

ZIP_WITH_SOFTLINK = os.path.join(_EGGINST_COMMON_DATA, "zip_with_softlink.zip")

VTK_EGG_DEFERRED_SOFTLINK = os.path.join(_EGGINST_COMMON_DATA, "VTK-5.10.1-1.egg")


@contextlib.contextmanager
def mkdtemp():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def create_venv(prefix):
    if os.environ.get("ENSTALLER_TEST_USE_VENV", None):
        cmd = ["venv", "-s", prefix]
    else:
        cmd = ["virtualenv", "-p", sys.executable, prefix]
    subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
