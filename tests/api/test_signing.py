"""Every offer and order record answered is signed, and anyone can check it with the published key (P12 W8).

Scores on Valio's "trust protocol" problem and the 15% "open, documented standards": a detached JSON Web Signature
(EdDSA over Ed25519) over the record's RFC 8785 canonical JSON, the key as a JSON Web Key set. The signature says
the gateway answered the record; with no key set it is a demo key and says so.
"""

from __future__ import annotations

import base64
import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tta.api import create_app
from tta.api.signing import JWKS_PATH, SET_KEY_NOTE, Signer, SigningKeyError, canonical_json, verifies
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _jwks(client: TestClient) -> dict[str, Any]:
    answer = client.get(JWKS_PATH)
    assert answer.status_code == 200 and answer.headers["content-type"] == "application/jwk-set+json"
    return answer.json()


# --- the canonical form ---------------------------------------------------------------------------------


def test_the_canonical_json_is_the_example_of_rfc_8785() -> None:
    # The example of RFC 8785, section 3.2.3 (its input and its canonical output), written down from memory:
    # the standards page checks it at the source.
    given = json.loads(
        '{"numbers": [333333333.33333329, 1E30, 4.50, 2e-3, 0.000000000000000000000000001],'
        ' "string": "\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/", "literals": [null, true, false]}'
    )

    assert canonical_json(given).decode() == (
        '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
    )


@pytest.mark.parametrize(("number", "written"), [
    (1.0, "1"), (1083.39, "1083.39"), (0.1, "0.1"), (1e21, "1e+21"), (1e-7, "1e-7"), (0.000001, "0.000001"),
    (123456789012345680000.0, "123456789012345680000"), (-0.0, "0"), (-2.5, "-2.5"), (100, "100"),
])
def test_numbers_are_written_as_ecmascript_writes_them(number: float, written: str) -> None:
    assert canonical_json(number).decode() == written


def test_a_number_that_is_not_finite_has_no_canonical_form() -> None:
    with pytest.raises(ValueError, match="canonical"):
        canonical_json(float("nan"))


# --- over REST ------------------------------------------------------------------------------------------


def test_an_offer_verifies_with_the_published_key_and_fails_on_a_changed_price(
    client: TestClient, scenario_1: dict[str, Any], make_offer: Flow
) -> None:
    offer = make_offer(client, "agent_hotel", scenario_1)
    keys = _jwks(client)

    assert verifies(offer, keys)
    cheaper = copy.deepcopy(offer)
    cheaper["options"][0]["lines"][0]["unit_net_price"] -= 0.01
    assert not verifies(cheaper, keys)
    more = copy.deepcopy(offer)
    more["options"][0]["lines"][0]["quantity"] += 1
    assert not verifies(more, keys)


def test_the_signature_is_checked_here_with_nothing_but_the_standards(
    client: TestClient, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    # What a buyer does, without this gateway's code: JWS detached content (RFC 7515, appendix F), EdDSA (RFC 8037).
    offer = make_offer(client, "agent_ward", scenario_2)
    proof = offer.pop("proof")
    [key] = _jwks(client)["keys"]
    header, empty_payload, signature = proof["jws"].split(".")

    assert (key["kty"], key["crv"], key["alg"], key["use"]) == ("OKP", "Ed25519", "EdDSA", "sig")
    assert key["kid"] == proof["key_id"]
    # The protected header also says what kind of record was signed and whether the key is a demo key (M2).
    assert empty_payload == "" and json.loads(_decode(header)) == {
        "alg": "EdDSA", "kid": proof["key_id"], "typ": "tta-offer+jws", "demo_key": True,
    }
    assert key["demo_key"] is True and proof["key_id"].startswith("demo-")
    assert (proof["type"], proof["algorithm"], proof["canonicalization"]) == ("JsonWebSignature", "EdDSA", "RFC 8785")
    signed = f"{header}.{_b64url(canonical_json(offer))}".encode()
    Ed25519PublicKey.from_public_bytes(_decode(key["x"])).verify(_decode(signature), signed)  # raises when invalid


def test_an_order_record_is_signed_when_placed_read_listed_and_decided(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow
) -> None:
    offer = make_offer(client, "agent_hotel", scenario_1)
    placed = place_order(client, "agent_hotel", offer, "signed-1")
    keys = _jwks(client)
    read = client.get(f"/v1/orders/{placed['order_id']}", headers=auth("agent_hotel")).json()
    [listed] = client.get("/v1/orders", headers=auth("agent_hotel")).json()
    again = client.get(f"/v1/offers/{offer['offer_id']}", headers=auth("agent_hotel")).json()

    for record in (placed, read, listed, again):
        assert verifies(record, keys)
    forged = {**placed, "status": "ORDERED"}
    assert placed["status"] == "PENDING_APPROVAL" and not verifies(forged, keys)

    order = placed
    for who in ("hotel_purchasing", "hotel_finance", "hotel_dietitian"):
        if order["status"] != "PENDING_APPROVAL":
            break
        order = client.post(
            f"/v1/approvals/{placed['approval_id']}/decision", json={"decision": "APPROVE"}, headers=auth(who)
        ).json()
    # P16 PAY-3: the person's confirmation is inside the signed record (who and role in the sentence, the time,
    # the option and its total).
    assert order["status"] == "ORDERED" and verifies(order, keys)
    assert "approval by" in order["status_sentence"] and order["option"]["totals"]["net"] > 0
    assert not verifies({**order, "status_sentence": order["status_sentence"].replace("Hanna", "Nobody")}, keys)


def test_what_is_stored_and_what_the_trail_holds_carry_no_proof(
    client: TestClient, parts: Any, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)

    assert offer["proof"] is not None
    assert parts.store.get_offer(offer["offer_id"]).proof is None
    assert "JsonWebSignature" not in "".join(event.model_dump_json() for event in parts.store.list_audit_events())


def test_with_no_key_set_the_key_is_a_demo_key_and_every_answer_says_so(
    client: TestClient, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    proof = make_offer(client, "agent_ward", scenario_2)["proof"]
    signing = client.get("/healthz").json()["signing"]

    assert proof["demo_key"] is True and "demo key" in proof["note"] and "nothing is claimed" in proof["note"]
    assert signing["demo_key"] is True and "demo key" in signing["note"].lower()
    assert (signing["key_id"], signing["algorithm"], signing["jwks_path"]) == (proof["key_id"], "EdDSA", JWKS_PATH)
    assert client.get("/healthz").json()["settings"]["signing_key_set"] is False


def test_a_key_from_the_setting_signs_and_is_never_shown(
    tmp_path: Path, catalog: ProductCatalog, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    private = Ed25519PrivateKey.generate()
    seed = _b64url(private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_signing_key=seed)

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        offer = make_offer(client, "agent_ward", scenario_2)
        health, keys = client.get("/healthz"), _jwks(client)

    assert offer["proof"]["demo_key"] is False and "not Valio Aimo" in offer["proof"]["note"]
    assert verifies(offer, keys) and "d" not in keys["keys"][0]  # the private part is never in the key set
    assert health.json()["signing"]["demo_key"] is False and health.json()["settings"]["signing_key_set"] is True
    assert seed not in health.text and seed not in repr(settings) and seed not in json.dumps(keys)
    assert Signer.from_setting(settings.tta_signing_key).key_id == offer["proof"]["key_id"]  # the same key each start


@pytest.mark.parametrize("bad", ["not base64 at all!", _b64url(b"too short"), _b64url(b"x" * 33)])
def test_a_key_that_is_not_an_ed25519_seed_stops_the_start_without_repeating_it(
    tmp_path: Path, catalog: ProductCatalog, bad: str
) -> None:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_signing_key=bad)

    with pytest.raises(SigningKeyError) as stopped:
        build_parts(settings, catalog=catalog)

    assert bad not in str(stopped.value) and "TTA_SIGNING_KEY" in str(stopped.value)


def test_a_record_signed_by_another_key_does_not_verify(
    client: TestClient, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    other = Signer.from_setting(None)

    assert not verifies(offer, other.jwks)
    assert not verifies({**offer, "proof": other.proof_of(offer).model_dump(mode="json")}, _jwks(client))
    assert not verifies({**offer, "proof": None}, _jwks(client))


def test_the_key_set_and_the_proof_are_documented(client: TestClient) -> None:
    document, text = client.get("/openapi.json").json(), client.get("/llms.txt").text

    assert "get" in document["paths"][JWKS_PATH] and "security" not in document["paths"][JWKS_PATH]["get"]
    assert "proof" in document["components"]["schemas"]["Offer"]["properties"]
    assert "proof" in document["components"]["schemas"]["Order"]["properties"]
    assert "RFC 8785" in document["info"]["description"] and JWKS_PATH in text
    assert "not that Valio Aimo signed it" in text


# --- what is signed says which key and which kind of record (review M2) ---------------------------------


def test_a_demo_signed_record_cannot_be_relabelled_as_signed_with_a_set_key(
    client: TestClient, scenario_1: dict[str, Any], make_offer: Flow
) -> None:
    offer, keys = make_offer(client, "agent_hotel", scenario_1), _jwks(client)
    assert offer["proof"]["demo_key"] is True and verifies(offer, keys)

    relabelled = {**offer, "proof": {**offer["proof"], "demo_key": False, "note": SET_KEY_NOTE}}
    other_note = {**offer, "proof": {**offer["proof"], "note": "Signed by Valio Aimo."}}
    other_path = {**offer, "proof": {**offer["proof"], "jwks_path": "/somewhere/else.json"}}

    assert not verifies(relabelled, keys)
    assert not verifies(other_note, keys)
    assert not verifies(other_path, keys)


def test_the_demo_marker_is_in_the_signed_header_the_key_id_and_the_published_key() -> None:
    demo, private = Signer.from_setting(None), Ed25519PrivateKey.generate()
    seed = _b64url(private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
    fixed = Signer.from_setting(SecretStr(seed))
    record = {"offer_id": "o-1", "total": 3}

    for signer, is_demo in ((demo, True), (fixed, False)):
        proof = signer.proof_of(record).model_dump(mode="json")
        header = json.loads(_decode(proof["jws"].split(".")[0]))
        [key] = signer.jwks["keys"]
        assert header["demo_key"] is is_demo and key["demo_key"] is is_demo and proof["demo_key"] is is_demo
        assert proof["key_id"].startswith("demo-") is is_demo and key["kid"] == header["kid"] == proof["key_id"]
        assert verifies({**record, "proof": proof}, signer.jwks)
    # A key set that hides the marker, or states the other one, is not the set this record was signed for.
    proof = demo.proof_of(record).model_dump(mode="json")
    [key] = demo.jwks["keys"]
    assert not verifies({**record, "proof": proof}, {"keys": [{**key, "demo_key": False}]})
    assert not verifies({**record, "proof": proof}, {"keys": [{k: v for k, v in key.items() if k != "demo_key"}]})


def test_a_signature_over_an_offer_cannot_be_presented_as_an_order_and_the_other_way() -> None:
    signer = Signer.from_setting(None)
    offer, order = {"offer_id": "o-1", "total": 3}, {"order_id": "r-1", "offer_id": "o-1", "total": 3}
    offer_proof = signer.proof_of(offer).model_dump(mode="json")
    order_proof = signer.proof_of(order).model_dump(mode="json")

    assert json.loads(_decode(offer_proof["jws"].split(".")[0]))["typ"] == "tta-offer+jws"
    assert json.loads(_decode(order_proof["jws"].split(".")[0]))["typ"] == "tta-order+jws"
    assert verifies({**offer, "proof": offer_proof}, signer.jwks)
    assert verifies({**order, "proof": order_proof}, signer.jwks)
    # The same content with the other kind's header: the signature was made over another header, and the header
    # of the proof given does not name this kind of record.
    assert not verifies({**offer, "proof": order_proof}, signer.jwks)
    assert not verifies({**order, "proof": offer_proof}, signer.jwks)
    header, _, signature = offer_proof["jws"].partition("..")
    swapped = order_proof["jws"].partition("..")[0] + ".." + signature
    assert not verifies({**offer, "proof": {**offer_proof, "jws": swapped}}, signer.jwks)


def test_a_record_that_is_neither_an_offer_nor_an_order_is_not_signed() -> None:
    with pytest.raises(TypeError):
        Signer.from_setting(None).proof_of({"something": "else"})
