"""The offer service: the `OfferBuilder` and `OfferRevalidator` ports over the functions of this package."""

from __future__ import annotations

from tta.contracts.availability import RevalidationResult
from tta.contracts.common import Identity
from tta.contracts.errors import NotAuthorised
from tta.contracts.offer import Offer, OfferOption, SubstituteQuery, SubstituteResult
from tta.contracts.policy import BuyerProfile
from tta.contracts.request import PurchaseRequest
from tta.offers.builder import build_offer
from tta.offers.deps import OfferDeps
from tta.offers.revalidation import revalidate
from tta.offers.substitutes import find_substitutes


class OfferService:
    """Implements `tta.contracts.ports.OfferBuilder` and `OfferRevalidator`. Holds no state of its own."""

    def __init__(self, deps: OfferDeps) -> None:
        self._deps = deps

    def build_offer(self, request: PurchaseRequest, identity: Identity) -> Offer:
        profile = self._profile_of(identity)
        return build_offer(request, profile, self._deps, agent_id=identity.id)

    def find_substitutes(self, product_id: str, identity: Identity, query: SubstituteQuery) -> SubstituteResult:
        return find_substitutes(product_id, self._profile_of(identity), self._deps, query)

    def revalidate(self, option: OfferOption) -> RevalidationResult:
        return revalidate(option, self._deps)

    def _profile_of(self, identity: Identity) -> BuyerProfile:
        """The buyer profile is never a request field: it comes from the caller's identity (SPEC section 2)."""
        if identity.profile_id is None:
            raise NotAuthorised("This caller is not bound to a buyer profile, so no offer can be built for it.")
        return self._deps.policy.get_profile(identity.profile_id)
