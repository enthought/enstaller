import logging
import os.path

import egginst._compat

from egginst.main import EggInst, get_installed, name_version_fn  # noqa

logging.getLogger("egginst").addHandler(egginst._compat.NullHandler())

POST_INSTALL_LIB = os.path.join(os.path.dirname(__file__), "_post_install_lib.py")
