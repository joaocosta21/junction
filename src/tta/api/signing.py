"""Signed offers and order records (P12 W8, with P16 PAY-3): what the gateway said, checkable later by anyone.

Scores on Valio's "trust protocol" problem (what an agent can trust without a manual check) and the 15% "open,
documented standards rather than a proprietary format". Every offer and every order record the REST routes and
the MCP tools answer carries a `proof`: a detached JSON Web Signature (RFC 7515, appendix F) with the algorithm
EdDSA over Ed25519 (RFC 8037), over the record's canonical JSON as RFC 8785 defines it (JCS). The public key is
served as a JSON Web Key set (RFC 7517) at `/.well-known/jwks.json`; its `kid` is the key's thumbprint (RFC 7638),
with `demo-` in front when the gateway generated the key itself.

What is signed (review M2): the protected header and the record. The header holds `alg`, `kid`, `typ` (the kind of
record: `tta-offer+jws` or `tta-order+jws`, so a signature over one cannot be presented as the other) and
`demo_key`. The published key carries the same `demo_key`. The `proof` fields beside the signature (`key_id`,
`demo_key`, `note`, `jwks_path`) are not signed: `verifies` reads the truth from the header and refuses a proof
whose unsigned fields say anything else.

To check a record: take the JSON as it was answered, remove `proof`, write the rest as RFC 8785 says, and verify
`<header>.<base64url of those bytes>` against the signature, where `proof.jws` is `<header>..<signature>`.
A changed price, quantity, verdict or name no longer verifies.

What the signature says, and no more: **this gateway** answered this record. It does not say Valio Aimo signed
anything, and it is not a Verifiable Credential. The key comes from the setting `TTA_SIGNING_KEY` (the 32-byte
Ed25519 seed, base64url). With no key set a key is generated when the gateway starts: a demo key, said so in
every proof and in `/healthz`, gone at the next start, so nothing is claimed about a record signed with it.
An order record holds the person's confirmation in its status sentence (who, role), `updated_at`, the option and
its total: the shape of a signed checkout record, not an AP2 mandate. The RFCs are cited from memory (no web
reading was allowed in the build): the standards page checks them at the source.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
from decimal import Decimal
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import BaseModel, SecretStr

from tta.contracts.offer import PROOF_ALGORITHM, PROOF_CANONICALIZATION, Proof

JWKS_PATH = "/.well-known/jwks.json"
JWKS_MEDIA_TYPE = "application/jwk-set+json"  # RFC 7517, section 8.5.2
PROOF_FIELD = "proof"
SEED_BYTES = 32
KEY_SETTING = "TTA_SIGNING_KEY"
BAD_KEY = f"{KEY_SETTING} must be the 32-byte seed of an Ed25519 key, written as base64url. The value is not repeated."
DEMO_KEY_NOTE = (
    "Signed with a demo key this gateway generated when it started; it is gone at the next start, so nothing is "
    "claimed about this signature beyond this run."
)
SET_KEY_NOTE = "Signed by this gateway with the key its operator set. The gateway signed it, not Valio Aimo."
# ECMAScript writes a number without an exponent when its decimal exponent is in this range (RFC 8785, 3.2.2.3).
ES_MIN_PLAIN_EXPONENT, ES_MAX_PLAIN_EXPONENT = -6, 21
DEMO_KEY_ID_PREFIX = "demo-"  # in front of the thumbprint in the `kid` of a key the gateway generated itself
DEMO_KEY_MEMBER = "demo_key"  # in the protected header and in the published key: true for such a key
# The `typ` of the protected header (RFC 7515, 4.1.9) names the kind of record that was signed.
OFFER_TYPE, ORDER_TYPE = "tta-offer+jws", "tta-order+jws"
ORDER_ID_FIELD, OFFER_ID_FIELD = "order_id", "offer_id"
NOT_A_SIGNED_KIND = "Only an offer or an order record is signed: this record has neither an order_id nor an offer_id."


class SigningKeyError(RuntimeError):
    """The signing key that was set cannot be used, so the gateway does not start. Never repeats the key."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _es_number(value: float) -> str:
    """A finite number as ECMAScript's Number-to-String writes it, the form RFC 8785 requires."""
    if not math.isfinite(value):
        raise ValueError("a NaN or an infinity has no canonical JSON")
    if value == 0:
        return "0"
    sign, digits, exponent = Decimal(repr(value)).as_tuple()  # the shortest digits that read back as this number
    text = "".join(map(str, digits)).rstrip("0") or "0"
    point = len(digits) + int(exponent)  # the decimal point stands after this many digits
    prefix = "-" if sign else ""
    if ES_MIN_PLAIN_EXPONENT < point <= ES_MAX_PLAIN_EXPONENT:
        if point <= 0:
            return f"{prefix}0.{'0' * -point}{text}"
        if point >= len(text):
            return f"{prefix}{text}{'0' * (point - len(text))}"
        return f"{prefix}{text[:point]}.{text[point:]}"
    mantissa = text[0] + ("." + text[1:] if len(text) > 1 else "")
    return f"{prefix}{mantissa}e{'+' if point > 0 else '-'}{abs(point - 1)}"


def _canonical(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, int):
        return _es_number(float(value)) if abs(value) >= 2**53 else str(value)
    if isinstance(value, float):
        return _es_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        # RFC 8785 sorts member names by their UTF-16 code units.
        names = sorted(value, key=lambda name: name.encode("utf-16-be"))
        members = (f"{json.dumps(name, ensure_ascii=False)}:{_canonical(value[name])}" for name in names)
        return "{" + ",".join(members) + "}"
    raise TypeError(f"{type(value).__name__} is not a JSON value")


def canonical_json(value: Any) -> bytes:
    """The JSON Canonicalization Scheme of RFC 8785: sorted member names, no white space, numbers as ECMAScript
    writes them, UTF-8. `value` is what a JSON parser gives (objects, arrays, strings, numbers, booleans, null)."""
    return _canonical(value).encode("utf-8")


def _without_proof(record: BaseModel | dict[str, Any]) -> dict[str, Any]:
    document = record.model_dump(mode="json") if isinstance(record, BaseModel) else dict(record)
    document.pop(PROOF_FIELD, None)
    return document


def _record_type(document: dict[str, Any]) -> str | None:
    """The `typ` of a record: an order has an `order_id` (and its offer's id too); an offer has an `offer_id`."""
    if document.get(ORDER_ID_FIELD):
        return ORDER_TYPE
    return OFFER_TYPE if document.get(OFFER_ID_FIELD) else None


def _signing_input(header: str, document: dict[str, Any]) -> bytes:
    return f"{header}.{_b64url(canonical_json(document))}".encode("ascii")


def _note(demo_key: bool) -> str:
    return DEMO_KEY_NOTE if demo_key else SET_KEY_NOTE


class Signer:
    """One Ed25519 key of the process. `demo_key` is true when the gateway generated it itself at start."""

    def __init__(self, key: Ed25519PrivateKey, *, demo_key: bool) -> None:
        self._key = key
        self.demo_key = demo_key
        public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self._jwk = {"crv": "Ed25519", "kty": "OKP", "x": _b64url(public)}
        # RFC 7638: SHA-256 over the required members of the key, in lexicographic order, with no white space.
        thumbprint = _b64url(hashlib.sha256(canonical_json(self._jwk)).digest())
        self.key_id = (DEMO_KEY_ID_PREFIX if demo_key else "") + thumbprint
        self._headers = {
            record_type: _b64url(canonical_json({
                "alg": PROOF_ALGORITHM, "kid": self.key_id, "typ": record_type, DEMO_KEY_MEMBER: demo_key,
            }))
            for record_type in (OFFER_TYPE, ORDER_TYPE)
        }

    @classmethod
    def from_setting(cls, seed: SecretStr | None) -> Signer:
        """The key of the setting, or a new demo key when none is set. Raises `SigningKeyError` for a value that
        is not a 32-byte seed in base64url."""
        if seed is None or not seed.get_secret_value().strip():
            return cls(Ed25519PrivateKey.generate(), demo_key=True)
        try:
            raw = _b64url_decode(seed.get_secret_value().strip())
        except (ValueError, binascii.Error):
            raise SigningKeyError(BAD_KEY) from None
        if len(raw) != SEED_BYTES:
            raise SigningKeyError(BAD_KEY)
        return cls(Ed25519PrivateKey.from_private_bytes(raw), demo_key=False)

    @property
    def jwks(self) -> dict[str, Any]:
        """The public key as a JSON Web Key set. `demo_key` is ours: true for a key generated at start."""
        key = {**self._jwk, "kid": self.key_id, "alg": PROOF_ALGORITHM, "use": "sig", DEMO_KEY_MEMBER: self.demo_key}
        return {"keys": [key]}

    def proof_of(self, record: BaseModel | dict[str, Any]) -> Proof:
        """The proof of an offer or an order record. Raises `TypeError` for anything else: nothing else is signed."""
        document = _without_proof(record)
        record_type = _record_type(document)
        if record_type is None:
            raise TypeError(NOT_A_SIGNED_KIND)
        header = self._headers[record_type]
        signature = self._key.sign(_signing_input(header, document))
        return Proof(
            key_id=self.key_id, jws=f"{header}..{_b64url(signature)}", jwks_path=JWKS_PATH,
            demo_key=self.demo_key, note=_note(self.demo_key),
        )

    def signed[Record: BaseModel](self, record: Record) -> Record:
        """A copy of an offer or an order with its `proof`. The stored record and the audit trail never hold one."""
        return record.model_copy(update={PROOF_FIELD: self.proof_of(record)})


def _signed_facts(header: str, document: dict[str, Any], key: dict[str, Any]) -> bool | None:
    """Whether the key is a demo key, as the protected header says it; `None` when the header is not one this
    gateway writes for this record and this key: another algorithm, key id or kind of record, a marker that is
    not true or false, or one the key id or the published key contradicts."""
    named = json.loads(_b64url_decode(header))
    if not isinstance(named, dict) or set(named) != {"alg", "kid", "typ", DEMO_KEY_MEMBER}:
        return None
    demo_key = named[DEMO_KEY_MEMBER]
    said_alike = (
        isinstance(demo_key, bool)
        and named["alg"] == PROOF_ALGORITHM
        and named["kid"] == key.get("kid")
        and named["typ"] == _record_type(document)
        and str(named["kid"]).startswith(DEMO_KEY_ID_PREFIX) is demo_key
        and key.get(DEMO_KEY_MEMBER) is demo_key
    )
    return demo_key if said_alike else None


def _unsigned_fields_agree(proof: dict[str, Any], demo_key: bool) -> bool:
    """The fields of `proof` that no signature covers must repeat what the signed header says, word for word."""
    return (
        proof.get("demo_key") is demo_key and proof.get("note") == _note(demo_key)
        and proof.get("jwks_path") == JWKS_PATH
    )


def verifies(record: dict[str, Any], jwks: dict[str, Any]) -> bool:
    """True when the record's `proof` is a valid signature of the record by a key of the set, over a header that
    names this kind of record, and nothing in the proof contradicts what was signed. The check a buyer makes with
    the published key: nothing here needs the gateway. Whether the key is a demo key is read from the signed
    header, never from `proof.demo_key` or `proof.note`."""
    proof = record.get(PROOF_FIELD)
    if not isinstance(proof, dict) or proof.get("algorithm") != PROOF_ALGORITHM:
        return False
    if proof.get("canonicalization") != PROOF_CANONICALIZATION:
        return False
    header, _, signature = str(proof.get("jws", "")).partition("..")
    keys = [key for key in jwks.get("keys", ()) if key.get("kid") == proof.get("key_id")]
    if not header or not signature or len(keys) != 1:
        return False
    document = _without_proof(record)
    try:
        demo_key = _signed_facts(header, document, keys[0])
        if demo_key is None or not _unsigned_fields_agree(proof, demo_key):
            return False
        public = Ed25519PublicKey.from_public_bytes(_b64url_decode(keys[0]["x"]))
        public.verify(_b64url_decode(signature), _signing_input(header, document))
    except (InvalidSignature, ValueError, KeyError, TypeError, binascii.Error):
        return False
    return True
