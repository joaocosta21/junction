"""Who is calling: a bearer token maps to exactly one identity (SPEC section 2).

Scores on the 20% "autonomy and controls": an agent is bound to one buyer profile by its token and can never
name another, an approver is a different identity from the agent whose order it decides, and the supplier
reads only its own view of the audit trail.

Demonstration tokens (`demo_tokens.yaml`, public by design) are loaded only when `TTA_ENV` is `dev` or
`demo`. Anywhere else the tokens come from the environment and the gateway refuses to start without them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.errors import Unauthenticated

DEMO_TOKENS_PATH = Path(__file__).with_name("demo_tokens.yaml")
TOKENS_VARIABLE = "TTA_TOKENS"
BEARER_SCHEME_NAME = "bearerAuth"
DEMO_TOKEN_NAMES = (
    "demo-agent-hotel-kitchen", "demo-agent-allergy-ward", "demo-agent-school-kitchen", "demo-agent-bakery-cafe",
    "demo-approver-hotel-purchasing", "demo-approver-ward-dietitian", "demo-approver-ward-purchasing",
    "demo-approver-school-purchasing", "demo-approver-school-dietitian",
    "demo-approver-bakery-owner", "demo-supplier-valio-aimo",
)  # the keys of `demo_tokens.yaml`, in its order: a test holds the two together
BEARER_DESCRIPTION = (
    "`Authorization: Bearer <token>`. One token is one identity: an **agent** bound to one buyer profile, an "
    "**approver** with one or more roles, or the **supplier** reader. In the `dev` and `demo` environments the "
    "demonstration tokens work. They are **public by design**, listed in `src/tta/api/demo_tokens.yaml`: "
    + ", ".join(f"`{name}`" for name in DEMO_TOKEN_NAMES[:-1]) + f" and `{DEMO_TOKEN_NAMES[-1]}`. "
    "Four customers (hotel kitchen, allergy ward, school kitchen, bakery and café), each with one agent and its "
    "people. One person confirms: the hotel's purchasing manager and the bakery's owner hold every role; the ward "
    "and the school have a dietitian besides, for allergen questions only. "
    "In any other environment tokens come from the environment and the demonstration tokens do not exist."
)
# A token from the environment is a secret someone chose: shorter than this it can be guessed. The
# demonstration tokens are public by design and are not held to it.
MIN_TOKEN_CHARACTERS = 24
NO_TOKEN = "This route needs a bearer token: send the header 'Authorization: Bearer <token>'."  # noqa: S105
UNKNOWN_TOKEN = "The bearer token is not one this gateway issued."  # noqa: S105


class TokenConfigurationError(RuntimeError):
    """The tokens cannot be used, so the gateway does not start. The message never repeats a token."""


class TokenRegistry:
    """The known tokens and the identity behind each. Only a digest of each token is kept."""

    def __init__(self, identity_by_token: Mapping[str, Identity]) -> None:
        self._entries = tuple((_digest(token), identity) for token, identity in identity_by_token.items())

    @property
    def identities(self) -> tuple[Identity, ...]:
        return tuple(identity for _, identity in self._entries)

    def identify(self, token: str) -> Identity | None:
        """The identity of a token, or `None`. Every known token is compared, in constant time, hit or miss."""
        presented = _digest(token)
        found: Identity | None = None
        for known, identity in self._entries:
            if hmac.compare_digest(presented, known):
                found = identity
        return found


def _digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


class _Entries(list[tuple[str, Any]]):
    """A JSON object as its pairs in the order written, so that a key given twice is still seen."""


def load_tokens(settings: Settings, profile_ids: Iterable[str]) -> TokenRegistry:
    """The registry for this environment. Raises `TokenConfigurationError` when there is no usable token."""
    if settings.is_demo_environment:
        raw: Any = yaml.safe_load(DEMO_TOKENS_PATH.read_text(encoding="utf-8"))
        entries = list(raw.items()) if isinstance(raw, dict) else None
        return TokenRegistry(_identities(entries, frozenset(profile_ids), source=DEMO_TOKENS_PATH.name))
    if settings.tta_tokens is None or not settings.has_tokens:
        raise TokenConfigurationError(
            f"{TOKENS_VARIABLE} is not set. Outside the dev and demo environments the gateway issues no "
            "demonstration token and does not start without tokens of its own."
        )
    try:
        raw = json.loads(settings.tta_tokens.get_secret_value(), object_pairs_hook=_Entries)
    except (ValueError, RecursionError):
        # The parser's message can quote the text it read, and that text holds the tokens.
        raise TokenConfigurationError(f"{TOKENS_VARIABLE} is not valid JSON.") from None
    entries = raw if isinstance(raw, _Entries) else None
    found = _identities(entries, frozenset(profile_ids), source=TOKENS_VARIABLE)
    _check_secrets(entries or (), found, source=TOKENS_VARIABLE)
    return TokenRegistry(found)


def _fields(value: Any) -> Any:
    """An identity as a plain object. `None` when it gives a field twice: which of the two is meant?"""
    if not isinstance(value, _Entries):
        return value
    names = [name for name, _ in value]
    return None if len(set(names)) != len(names) else {name: _fields(inner) for name, inner in value}


def _identities(
    entries: Sequence[tuple[Any, Any]] | None, profile_ids: frozenset[str], *, source: str
) -> dict[str, Identity]:
    """Token -> identity from untrusted configuration. An error names the position of an entry, never its token."""
    if not entries:
        raise TokenConfigurationError(f"{source} must be a JSON object that maps each token to an identity.")
    found: dict[str, Identity] = {}
    for position, (token, fields) in enumerate(entries, start=1):
        if not isinstance(token, str) or not token.strip():
            raise TokenConfigurationError(f"{source}: entry {position} has an empty token.")
        try:
            identity = Identity.model_validate(_fields(fields))
        except ValidationError as error:
            wrong = sorted({".".join(str(part) for part in item["loc"]) or "identity" for item in error.errors()})
            raise TokenConfigurationError(
                f"{source}: entry {position} is not a valid identity (check: {', '.join(wrong)})."
            ) from None
        if identity.profile_id is not None and identity.profile_id not in profile_ids:
            raise TokenConfigurationError(f"{source}: entry {position} names a buyer profile that does not exist.")
        found[token] = identity
    return found


def _check_secrets(entries: Sequence[tuple[str, Any]], found: Mapping[str, Identity], *, source: str) -> None:
    """What holds for tokens from the environment only: long enough, each token once, each identity once.
    One token is one identity, and the limits and the audit trail count by identity id."""
    tokens: dict[str, int] = {}
    identity_ids: dict[str, int] = {}
    for position, (token, _) in enumerate(entries, start=1):
        if len(token) < MIN_TOKEN_CHARACTERS:
            raise TokenConfigurationError(
                f"{source}: entry {position} has a token shorter than {MIN_TOKEN_CHARACTERS} characters."
            )
        if token in tokens:
            raise TokenConfigurationError(f"{source}: entries {tokens[token]} and {position} have the same token.")
        tokens[token] = position
        identity_id = found[token].id
        if identity_id in identity_ids:
            raise TokenConfigurationError(
                f"{source}: entries {identity_ids[identity_id]} and {position} have the same identity id."
            )
        identity_ids[identity_id] = position


_bearer = HTTPBearer(scheme_name=BEARER_SCHEME_NAME, description=BEARER_DESCRIPTION, auto_error=False)


def current_identity(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> Identity:
    """FastAPI dependency: the identity of the caller's bearer token, or `Unauthenticated` (401)."""
    if credentials is None or not credentials.credentials:
        raise Unauthenticated(NO_TOKEN)
    registry: TokenRegistry = request.app.state.parts.tokens
    identity = registry.identify(credentials.credentials)
    if identity is None:
        raise Unauthenticated(UNKNOWN_TOKEN)
    return identity


Caller = Annotated[Identity, Depends(current_identity)]
