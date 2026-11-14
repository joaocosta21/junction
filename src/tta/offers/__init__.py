"""Candidates to options: ranking, combining and substitutes (SPEC section 5).

`OfferService(OfferDeps(...))` implements the `OfferBuilder` and `OfferRevalidator` ports.
The same logic as functions: `build_offer(request, profile, deps, agent_id=...)`,
`find_substitutes(product_id, profile, deps, query)` and `revalidate(option, deps)`.
"""

from tta.offers.builder import build_offer
from tta.offers.deps import OfferDeps
from tta.offers.revalidation import revalidate
from tta.offers.service import OfferService
from tta.offers.substitutes import find_substitutes

__all__ = ["OfferDeps", "OfferService", "build_offer", "find_substitutes", "revalidate"]
