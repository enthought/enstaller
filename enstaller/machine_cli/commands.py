import argparse
import json
import sys

from egginst.progress import console_progress_manager_factory

from enstaller import Configuration, Session
from enstaller.cli.utils import install_req, repository_factory
from enstaller.enpkg import Enpkg, ProgressBarContext
from enstaller.errors import EnstallerException
from enstaller.solver import Requirement
from enstaller.vendor import jsonschema

from .json_schemas import INSTALL_SCHEMA


_REQUIREMENT = "requirement"
_AUTHENTICATION = "authentication"
_AUTHENTICATION_KIND = "kind"


class _FakeOpts(object):
    pass


def install_parse_json_string(json_string):
    json_data = json.loads(json_string)

    try:
        jsonschema.validate(json_data, INSTALL_SCHEMA)
    except jsonschema.ValidationError as e:
        msg = "Invalid configuration: {0!r}".format(e.message)
        raise EnstallerException(msg)

    requirement_string = json_data[_REQUIREMENT]
    authentication_data = json_data["authentication"]
    authentication_kind = authentication_data[_AUTHENTICATION_KIND]

    config = Configuration()
    if authentication_kind == "simple":
        config.update(auth=(authentication_data["username"],
                            authentication_data["password"]))
    else:
        msg = "Unsupported authentication kind: {0!r}". \
              format(authentication_kind)
        raise EnstallerException(msg)
    config.set_repositories_from_names(json_data["repositories"])

    requirement = Requirement.from_anything(requirement_string)

    return config, requirement


def install(json_string):
    config, requirement = install_parse_json_string(json_string)

    session = Session.authenticated_from_configuration(config)
    repository = repository_factory(session, config.indices)

    def fetch_progress_factory(*a, **kw):
        return console_progress_manager_factory(*a, show_speed=True, **kw)

    progress_bar_context = ProgressBarContext(console_progress_manager_factory,
                                              fetch=fetch_progress_factory)
    enpkg = Enpkg(repository, session, [sys.prefix], progress_bar_context, False)

    opts = _FakeOpts()
    opts.yes = False
    opts.force = False
    opts.forceall = False
    opts.no_deps = False

    install_req(enpkg, config, requirement, opts)


def handle_args(argv):
    p = argparse.ArgumentParser()
    subparsers = p.add_subparsers(help='sub-command help')

    install_p = subparsers.add_parser("install")
    install_p.add_argument("args_as_json",
                           help="The json arguments")
    install_p.set_defaults(func=install)

    return p.parse_args(argv)


def main(argv=None):
    argv = argv or sys.argv[1:]

    namespace = handle_args(argv)
    namespace.func(namespace.args_as_json)

    sys.exit(0)
