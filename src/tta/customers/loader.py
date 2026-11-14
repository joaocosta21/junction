"""The customer files: one YAML file per customer in `data/`, checked when they load (P1 C2).

Every load checks the shape of each file and that each product type it names is one the catalog has. A load
that is given a catalog also checks every product id against the product file (`tta.customers.checks`).

Every file is synthetic and says so (`synthetic: true`). The file name is the customer id, which is the id of its
buyer profile. A folder with a file that fails any check does not load, and the error lists every problem.
Data files are untrusted input: they are read with `yaml.safe_load` and validated, never executed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

import yaml
from pydantic import ValidationError

from tta.contracts.customer import Customer
from tta.contracts.ports import Catalog
from tta.customers.checks import catalog_problems, type_problems

CUSTOMERS_DIR = Path(__file__).resolve().parent / "data"
FILE_SUFFIX = ".yaml"


class CustomerLoadError(ValueError):
    """The customer files cannot be used. `problems` lists every reason."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("The customer files cannot be loaded: " + "; ".join(self.problems))


def _first_lines(error: ValidationError) -> str:
    """Each validation error in one short clause: where, and what."""
    return "; ".join(
        f"{'.'.join(str(part) for part in detail['loc']) or 'file'}: {detail['msg']}" for detail in error.errors()
    )


def _read(path: Path) -> tuple[Customer | None, str | None]:
    """One customer file, or the reason it cannot be used."""
    name = path.stem
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        return None, f"{name}: the file cannot be read as YAML ({type(error).__name__})"
    if not isinstance(data, dict):
        return None, f"{name}: the file must hold one mapping"
    try:
        customer = Customer.model_validate(data)
    except ValidationError as error:
        return None, f"{name}: {_first_lines(error)}"
    if customer.customer_id != name:
        return None, f"{name}: the file is named {name} but holds the customer {customer.customer_id}"
    return customer, None


def load_customers(directory: Path = CUSTOMERS_DIR, catalog: Catalog | None = None) -> Mapping[str, Customer]:
    """Every customer of the folder, by id. Raises `CustomerLoadError` listing every problem.

    `catalog`: when given, every product id of each file must be in the product file and of the product type
    the file says; no supplier is called."""
    paths = sorted(directory.glob(f"*{FILE_SUFFIX}")) if directory.is_dir() else []
    if not paths:
        raise CustomerLoadError([f"there is no customer file in {directory.name}"])
    customers: dict[str, Customer] = {}
    problems: list[str] = []
    for path in paths:
        customer, problem = _read(path)
        if problem is not None:
            problems.append(problem)
        elif customer is not None:
            customers[customer.customer_id] = customer
            problems.extend(type_problems(customer))
            if catalog is not None:
                problems.extend(catalog_problems(customer, catalog))
    if problems:
        raise CustomerLoadError(problems)
    return MappingProxyType(customers)


@lru_cache(maxsize=1)
def shipped_customers() -> Mapping[str, Customer]:
    """The four shipped customers, checked. Raises `CustomerLoadError`."""
    return load_customers(CUSTOMERS_DIR)


def shipped_customer(customer_id: str) -> Customer | None:
    """One shipped customer, or None for an id that has no file."""
    return shipped_customers().get(customer_id)
