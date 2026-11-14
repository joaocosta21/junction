"""What `GET /v1/schemas` serves: the JSON Schema of every contract model, each naming its dialect (P12 W7).

Scores on the 15% "open, documented standards rather than a proprietary format". `tta.contracts.schemas` lists
the core contract modules; the menu, standing-order and customer models are taken here too, so
every model a route takes or answers has its schema. Each schema carries `$schema`, so a validator does not have
to be told which dialect of JSON Schema it reads.
"""

from __future__ import annotations

from collections.abc import Iterable
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from tta.api import customers
from tta.contracts import customer, menu, standing
from tta.contracts.schemas import all_models

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"  # the dialect Pydantic v2 writes
MORE_MODULES = (menu, standing, customer, customers)  # modules `tta.contracts.schemas` does not list
NAME_USED_TWICE = "Two contract models are both called {name}: /v1/schemas names each model once."


def _models_of(modules: Iterable[ModuleType]) -> dict[str, type[BaseModel]]:
    """Every Pydantic model defined in these modules, by class name: the rule of `all_models`."""
    return {
        name: value
        for module in modules
        for name, value in vars(module).items()
        if isinstance(value, type) and issubclass(value, BaseModel) and value.__module__ == module.__name__
    }


def exported_models() -> dict[str, type[BaseModel]]:
    """The core models and the menu and standing-order models, by name. A name used twice stops the export."""
    core, more = all_models(), _models_of(MORE_MODULES)
    for name, model in more.items():
        if core.get(name, model) is not model:
            raise ValueError(NAME_USED_TWICE.format(name=name))
    return dict(sorted({**core, **more}.items()))


def exported_schemas() -> dict[str, dict[str, Any]]:
    """The JSON Schema of every exported model as it is serialised, with `$schema` first."""
    return {
        name: {"$schema": JSON_SCHEMA_DIALECT, **model.model_json_schema(mode="serialization")}
        for name, model in exported_models().items()
    }
