"""The demonstration's four customers: who orders, their usual products and their synthetic past orders (P1 C2).

`shipped_customers()` loads and checks the files of `data/` once. `tta.customers.checks` checks them against the
catalog and a recording; it is not imported here, so loading a customer needs neither. Every file is synthetic and
says so. Limits, allergen rules, substitution scope and who may approve are the buyer profiles' (`tta.policy`).
"""

from tta.customers.apply import preference_for
from tta.customers.loader import (
    CUSTOMERS_DIR,
    CustomerLoadError,
    load_customers,
    shipped_customer,
    shipped_customers,
)

__all__ = [
    "CUSTOMERS_DIR",
    "CustomerLoadError",
    "load_customers",
    "preference_for",
    "shipped_customer",
    "shipped_customers",
]
