"""Typed errors, one per problem type, and the RFC 9457 problem-details body (SPEC section 2)."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

PROBLEM_TYPE_BASE = "https://tta.example/problems/"
PROBLEM_CONTENT_TYPE = "application/problem+json"


class ProblemDetails(BaseModel):
    """RFC 9457 body. Extension members are allowed, as the RFC provides."""

    model_config = ConfigDict(frozen=True, extra="allow")

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


class TtaError(Exception):
    """Base of every error the gateway reports to a caller. Never carries a secret or a stack trace."""

    slug: ClassVar[str] = "invalid-request"
    title: ClassVar[str] = "The request cannot be processed"
    status_code: ClassVar[int] = 400

    def __init__(self, detail: str, **extensions: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extensions = extensions

    @property
    def problem_type(self) -> str:
        return PROBLEM_TYPE_BASE + self.slug

    def to_problem(self, instance: str | None = None) -> ProblemDetails:
        return ProblemDetails(
            type=self.problem_type,
            title=self.title,
            status=self.status_code,
            detail=self.detail,
            instance=instance,
            **self.extensions,
        )


class InvalidRequest(TtaError):
    slug = "invalid-request"
    title = "The request is not valid"
    status_code = 422


class Unauthenticated(TtaError):
    """No token, or a token nobody issued. Reported with the `not-authorised` type and status 401."""

    slug = "not-authorised"
    title = "Authentication is required"
    status_code = 401


class NotAuthorised(TtaError):
    slug = "not-authorised"
    title = "This caller may not do this"
    status_code = 403


class UnknownProduct(TtaError):
    slug = "unknown-product"
    title = "The product is not in the catalog"
    status_code = 404


class NotFound(TtaError):
    slug = "not-found"
    title = "No such offer, order or approval"
    status_code = 404


class OfferExpired(TtaError):
    slug = "offer-expired"
    title = "The offer is no longer valid"
    status_code = 409


class OfferStale(TtaError):
    slug = "offer-stale"
    title = "Price or availability changed since the offer"
    status_code = 409


class PolicyBlocked(TtaError):
    slug = "policy-blocked"
    title = "The policy does not allow this order, even with approval"
    status_code = 422


class SupplierUnavailable(TtaError):
    slug = "supplier-unavailable"
    title = "A service the gateway depends on cannot be reached"
    status_code = 503


class RateLimited(TtaError):
    slug = "rate-limited"
    title = "Too many requests"
    status_code = 429


ALL_ERRORS: tuple[type[TtaError], ...] = (
    InvalidRequest,
    Unauthenticated,
    NotAuthorised,
    UnknownProduct,
    NotFound,
    OfferExpired,
    OfferStale,
    PolicyBlocked,
    SupplierUnavailable,
    RateLimited,
)
