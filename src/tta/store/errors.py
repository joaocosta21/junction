"""The store's own error. It belongs with the typed errors of `tta.contracts.errors` once that file can change."""

from __future__ import annotations

from tta.contracts.errors import SupplierUnavailable


class AuditChainConflict(SupplierUnavailable):
    """An audit event does not follow the last stored one: another writer appended first.

    Nothing was written. The writer reads the head again and tries once more. Reported to a caller as
    `supplier-unavailable` (503): the same request can be sent again.
    """
