"""The product ids of one question to the Valio API."""

from __future__ import annotations

from collections.abc import Sequence


def distinct_ids(product_ids: Sequence[str]) -> tuple[str, ...]:
    """The ids asked for, once each, in the order first seen.

    The API answers a repeated id once per occurrence (AIMO/docs/API.md section 8.9), so repeats
    only cost payload.
    """
    if isinstance(product_ids, str):
        raise TypeError("product ids must be a sequence of ids, not a single string")
    return tuple(dict.fromkeys(product_ids))
