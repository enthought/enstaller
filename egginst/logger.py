import logging

import egginst._compat


dry_run = logging.getLogger("egginst.dry_run")
dry_run.addHandler(egginst._compat.NullHandler())
