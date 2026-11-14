"""Every contract model by name, and their JSON Schemas (GET /v1/schemas)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from tta.contracts import agent, allergen, audit, availability, common, errors, offer, order, policy, product, request

_MODULES = (common, request, product, allergen, availability, policy, offer, order, audit, agent, errors)


def all_models() -> dict[str, type[BaseModel]]:
    """Every Pydantic model defined in the contracts package, by class name."""
    found: dict[str, type[BaseModel]] = {}
    for module in _MODULES:
        for name, value in vars(module).items():
            is_model = isinstance(value, type) and issubclass(value, BaseModel)
            if is_model and value.__module__ == module.__name__ and name != "Contract":
                found[name] = value
    return dict(sorted(found.items()))


def all_schemas() -> dict[str, dict[str, Any]]:
    """JSON Schema (draft 2020-12) of every contract model, as it is serialised."""
    return {name: model.model_json_schema(mode="serialization") for name, model in all_models().items()}
