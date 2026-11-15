"""Sentences about a candidate that is another kind of product by its name (decision B65; review C3-F2).

The reading is `tta.catalog.kind_words`; `tta.offers.substitutes` applies it. Words of a product name are text
of the product file: they enter a sentence through `plain_name`, with no quotation mark around them.
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.contracts.product import Product
from tta.offers.wording import counted, plain_name

# How the reason starts. A rule sentence that quotes the reasons of a substitute reads it as it stands.
KIND_REASON_PREFIX = "it is not shown to be the same kind of product: "


def kind_reason(not_said: Sequence[str]) -> str:
    """One reason of a replace check: the words of the original's name that say what it is, and that the
    candidate's name does not have."""
    words = plain_name(" ".join(not_said))
    return f"{KIND_REASON_PREFIX}its name does not say {words}, as the name of the product asked for does"


def other_kind_note(original: Product, left_out: int, candidates: int) -> tuple[str, ...]:
    """What the ranking says of the products it left out for their kind, and, when nothing is left to rank,
    that the product has no substitute: that is the answer, not a gap in it."""
    if not left_out:
        return ()
    name = plain_name(original.display_name)
    one = left_out == 1
    note = (
        f"{counted(left_out, 'product')} of the same category {'is' if one else 'are'} left out: by "
        f"{'its name it is' if one else 'their names they are'} another kind of product than {name}, and "
        f"{'is' if one else 'are'} never offered in its place."
    )
    if candidates:
        return (note,)
    return (note, f"No product can stand in for {name}: none of its category is the same kind of product by its name.")
