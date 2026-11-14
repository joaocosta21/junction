"""Hooks for what other packages add to the gateway. Each is an optional import: when the module is not
there, the gateway runs without it and `/healthz` says so.

The buyer agent (`tta.agent`, task T10) defines either or both of
    build_request_parser(*, settings, clock, product_type_keys) -> RequestParser
    build_agent_runner(*, settings, clock, product_type_keys) -> AgentRunner
`clock` is the data clock (pinned in replay), for "by Monday"; `product_type_keys` are the catalog's. With
one of the two the gateway starts and logs which is missing; a package that defines neither stops the start.

The MCP surface (`tta.api.mcp_surface`, task T11) and the pages (`tta.ui.routes`, task T12) each define
    create_surface(context: SurfaceContext) -> ASGI application
`create_app` mounts the MCP application at `/mcp` and the pages at `/`, and runs the application's own
lifespan together with the gateway's (the MCP session manager needs it). A surface calls `context.service`
and nothing else; the pages call the service of the visitor's own order book (`context.sandboxes`).

A module that exists but lacks what the gateway calls stops the start: a part that silently went missing
would only be noticed in front of a judge.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from starlette.types import ASGIApp

from tta.api.sandbox import Sandboxes
from tta.api.service import Gateway
from tta.api.signing import Signer
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.ports import AgentRunner, Clock, RequestParser
from tta.standing import StandingOrders

AGENT_MODULE = "tta.agent"
PARSER_FACTORY = "build_request_parser"
RUNNER_FACTORY = "build_agent_runner"
MCP_MODULE = "tta.api.mcp_surface"
PAGES_MODULE = "tta.ui.routes"
SURFACE_FACTORY = "create_surface"
AGENT_FACTORIES = (PARSER_FACTORY, RUNNER_FACTORY)

logger = logging.getLogger(__name__)


class HookError(RuntimeError):
    """An optional module is there but does not offer what the gateway calls. The gateway does not start."""


@dataclass(frozen=True)
class SurfaceContext:
    """What a surface gets. `demo_identities` and `sandboxes` are empty outside the dev and demo environments,
    so a page can act as a demonstration identity, in an order book of its visitor's own, only there."""

    settings: Settings
    service: Gateway  # the `GatewayService` port, plus `list_orders`: the shared book of the tokens
    identify: Callable[[str], Identity | None]  # bearer token -> identity, the same as the REST routes use
    demo_identities: tuple[Identity, ...] = ()
    sandboxes: Sandboxes | None = None  # a private order book per browser session (`tta.api.sandbox`)
    # The standing orders of the shared book, with the limits of a set-up: the one the REST routes serve. None when
    # a surface is built without the application (a test): the MCP tools that need it then refuse.
    standing: StandingOrders | None = None
    signer: Signer | None = None  # signs the offers and orders a tool answers; None: they are answered unsigned


def optional_module(name: str) -> ModuleType | None:
    """The module, or `None` when it does not exist. A module that exists and fails to import still fails."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name == name:
            return None
        raise


def _factory(module: ModuleType, factory_name: str) -> Callable[..., Any] | None:
    """The factory of the agent package, or `None` when the package has only the other one (logged, naming
    this one). Raises `HookError` when the package defines neither: that is a broken install, not "no agent"."""
    factory = getattr(module, factory_name, None)
    if callable(factory):
        return factory
    if not any(callable(getattr(module, name, None)) for name in AGENT_FACTORIES):
        raise HookError(
            f"{AGENT_MODULE} exists but defines neither {PARSER_FACTORY} nor {RUNNER_FACTORY}, so the gateway "
            "would run without a request parser and without a buyer agent."
        )
    logger.warning(
        "%s does not define %s: the gateway starts without it, and the route that needs it answers "
        "supplier-unavailable.", AGENT_MODULE, factory_name,
    )
    return None


def _built[Port](factory_name: str, port: type[Port], given: dict[str, Any]) -> Port | None:
    module = optional_module(AGENT_MODULE)
    factory = _factory(module, factory_name) if module is not None else None
    if factory is None:
        return None
    built = factory(**given)
    if not isinstance(built, port):
        raise HookError(f"{AGENT_MODULE}.{factory_name} must return an object with the {port.__name__} port.")
    return built


def request_parser(settings: Settings, clock: Clock, product_type_keys: tuple[str, ...]) -> RequestParser | None:
    given = {"settings": settings, "clock": clock, "product_type_keys": product_type_keys}
    return _built(PARSER_FACTORY, RequestParser, given)  # type: ignore[type-abstract]


def agent_runner(settings: Settings, clock: Clock, product_type_keys: tuple[str, ...]) -> AgentRunner | None:
    given = {"settings": settings, "clock": clock, "product_type_keys": product_type_keys}
    return _built(RUNNER_FACTORY, AgentRunner, given)  # type: ignore[type-abstract]


def surface(module_name: str, context: SurfaceContext) -> ASGIApp | None:
    """The ASGI application of an optional surface module, or `None` when the module does not exist."""
    module = optional_module(module_name)
    if module is None:
        return None
    factory = getattr(module, SURFACE_FACTORY, None)
    if not callable(factory):
        raise HookError(
            f"{module_name} exists but has no {SURFACE_FACTORY}(context) function, so it cannot be mounted."
        )
    return factory(context)
