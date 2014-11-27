import json
import sys

from egginst.progress import console_progress_manager_factory

from enstaller import Configuration, Session
from enstaller.cli.utils import install_req, repository_factory
from enstaller.enpkg import Enpkg, ProgressBarContext
from enstaller.errors import EnpkgError, EnstallerException
from enstaller.solver import Request, Requirement
from enstaller.vendor import jsonschema

from .json_schemas import INSTALL_SCHEMA, UPDATE_ALL_SCHEMA

import enstaller.cli.commands


_REQUIREMENT = "requirement"
_AUTHENTICATION = "authentication"
_AUTHENTICATION_KIND = "kind"


class _FakeOpts(object):
    pass


def fetch_progress_factory(*a, **kw):
    return console_progress_manager_factory(*a, show_speed=True, **kw)


def _config_from_json_data(json_data):
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
    config.update(store_url=json_data["store_url"])
    config.set_repositories_from_names(json_data["repositories"])

    return config


def update_all_parse_json_string(json_string):
    json_data = json.loads(json_string)

    try:
        jsonschema.validate(json_data, UPDATE_ALL_SCHEMA)
    except jsonschema.ValidationError as e:
        msg = "Invalid configuration: {0!r}".format(e.message)
        raise EnstallerException(msg)

    return _config_from_json_data(json_data)


def install_parse_json_string(json_string):
    json_data = json.loads(json_string)

    try:
        jsonschema.validate(json_data, INSTALL_SCHEMA)
    except jsonschema.ValidationError as e:
        msg = "Invalid configuration: {0!r}".format(e.message)
        raise EnstallerException(msg)

    config = _config_from_json_data(json_data)

    requirement_string = json_data[_REQUIREMENT]
    requirement = Requirement.from_anything(requirement_string)

    return config, requirement


def install(json_string):
    config, requirement = install_parse_json_string(json_string)

    session = Session.authenticated_from_configuration(config)
    repository = repository_factory(session, config.indices)

    progress_bar_context = ProgressBarContext(console_progress_manager_factory,
                                              fetch=fetch_progress_factory)
    enpkg = Enpkg(repository, session, [sys.prefix], progress_bar_context, False)

    opts = _FakeOpts()
    opts.yes = False
    opts.force = False
    opts.forceall = False
    opts.no_deps = False

    install_req(enpkg, config, requirement, opts)


def remove(json_string):
    config, requirement = install_parse_json_string(json_string)

    session = Session.authenticated_from_configuration(config)
    repository = repository_factory(session, config.indices)

    progress_bar_context = ProgressBarContext(console_progress_manager_factory,
                                              fetch=fetch_progress_factory)
    enpkg = Enpkg(repository, session, [sys.prefix], progress_bar_context, False)

    solver = enpkg._solver_factory()
    try:
        request = Request()
        request.remove(requirement)
        enpkg.execute(solver.resolve(request))
    except EnpkgError as e:
        print(str(e))


def update_all(json_string):
    config = update_all_parse_json_string(json_string)

    session = Session.authenticated_from_configuration(config)
    repository = repository_factory(session, config.indices)

    progress_bar_context = ProgressBarContext(console_progress_manager_factory,
                                              fetch=fetch_progress_factory)
    enpkg = Enpkg(repository, session, [sys.prefix], progress_bar_context, False)

    opts = _FakeOpts()
    opts.yes = False
    opts.force = False
    opts.forceall = False
    opts.no_deps = False

    enstaller.cli.commands.update_all(enpkg, config, opts)
