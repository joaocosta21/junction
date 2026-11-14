"""One way to report a data file the catalog cannot use.

The contracts have no error of their own for a broken data file, so the catalog raises
`SupplierUnavailable`: the gateway cannot answer without its product data. The message names the
file, never the folder it is in.
"""

from __future__ import annotations

from pathlib import Path

from tta.contracts.errors import SupplierUnavailable


def data_file_error(path: Path, reason: str) -> SupplierUnavailable:
    return SupplierUnavailable(f"The data file {path.name} cannot be used: {reason}", file=path.name)
