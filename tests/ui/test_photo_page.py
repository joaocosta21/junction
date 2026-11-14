"""The first page takes a photo of an order list next to the text box (task T18), and a fourth example.

Scores on the 30% demo and the 20% "precise match": a kitchen photographs its handwritten list; the page shows
what was read in it above the request as the gateway read it, then the run goes on as for typed text: offer,
verdict, order. The photo tests use the agent package as it ships, with no key: the demo photo's transcription
and reading are recorded (`fixtures/agent/`), so no model is called.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.catalog import ProductCatalog
from tta.config import REPO_ROOT, Settings
from tta.contracts.common import ApproverRole, OrderStatus
from tta.valio import ReplayGateway

MakeClient = Callable[..., TestClient]
Form = dict[str, str]
DEMO_PHOTO = REPO_ROOT / "fixtures" / "agent" / "photos" / "order-list.png"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(64)
HOTEL = "agent:hotel-kitchen"


@pytest.fixture
def agent_client(make_client: MakeClient, settings: Settings, catalog: ProductCatalog) -> TestClient:
    """The gateway with the agent package's own parser and runner, as the hooks build them with no key."""
    package = pytest.importorskip("tta.agent")
    assert not settings.has_gemini_key  # recordings only: no model is called
    given = {
        "settings": settings, "clock": ReplayGateway(settings.replay_capture_dir).clock,
        "product_type_keys": catalog.product_type_keys(),
    }
    return make_client(
        request_parser=package.build_request_parser(**given), agent_runner=package.build_agent_runner(**given)
    )


@pytest.fixture
def send_photo(form_fields: Callable[..., Form]) -> Callable[..., Any]:
    """Choose a file in the upload control and press its button: the form is sent as multipart/form-data."""

    def post(client: TestClient, photo: bytes, who: str = HOTEL, **fields: str) -> Any:
        form = {**form_fields(client), "who": who, "text": "", **fields}
        return client.post("/run-photo", data=form, files={"image": ("list.png", photo, "image/png")})

    return post


def test_the_first_page_has_a_photo_upload_next_to_the_text_box(client: TestClient) -> None:
    page = client.get("/").text

    upload = page.index('type="file"')
    assert page.index('id="text"') < upload < page.index('name="example"')
    assert 'name="image"' in page and 'accept="image/jpeg,image/png,image/webp,image/heic,image/heif"' in page
    assert 'formaction="/run-photo"' in page and 'formenctype="multipart/form-data"' in page
    assert "at most 5 MB" in page


def test_the_demo_photo_is_transcribed_read_and_run_and_its_lines_are_shown_above_the_parsed_request(
    agent_client: TestClient, send_photo: Callable[..., Any], only_order: Callable[..., Any]
) -> None:
    response = send_photo(agent_client, DEMO_PHOTO.read_bytes())
    page = response.text

    assert response.status_code == 200 and "/?offer=" in str(response.url)
    assert page.index('id="transcription"') < page.index('class="request-lines"')
    assert "<q>Tilaus</q>" in page and "<q>Maito laktoositon 1000 l — ma</q>" in page
    assert "Read from a photo: transcribed " in page and "no model was asked" in page
    assert "1,000 L" in page or "1000 L" in page
    assert "Sent for approval" in page
    assert only_order(agent_client).status is OrderStatus.PENDING_APPROVAL


def test_a_photo_form_sent_twice_orders_once(
    agent_client: TestClient, form_fields: Callable[..., Form], orders: Callable[..., tuple[Any, ...]]
) -> None:
    form = {**form_fields(agent_client), "who": HOTEL}
    photo = {"image": ("list.png", DEMO_PHOTO.read_bytes(), "image/png")}

    first = agent_client.post("/run-photo", data=form, files=photo)
    again = agent_client.post("/run-photo", data=form, files=photo)

    assert first.status_code == again.status_code == 200
    assert len(orders(agent_client)) == 1


@pytest.mark.parametrize(
    ("photo", "said"),
    [(b"%PDF-1.7\n" + bytes(64), "not a JPEG, PNG, WebP or HEIC image"),
     (PNG + bytes(5 * 1024 * 1024), "larger than 5 MB")],
    ids=["not-an-image", "over-5-mb"],
)
def test_an_upload_that_cannot_be_a_photo_is_refused_on_the_first_page_and_nothing_is_ordered(
    agent_client: TestClient, send_photo: Callable[..., Any], orders: Callable[..., tuple[Any, ...]],
    photo: bytes, said: str,
) -> None:
    response = send_photo(agent_client, photo)

    assert response.status_code == 422 and said in response.text
    assert orders(agent_client) == ()


def test_a_photo_the_parser_cannot_read_is_said_plainly(
    client: TestClient, send_photo: Callable[..., Any]
) -> None:
    response = send_photo(client, PNG)  # this gateway runs no parser at all

    assert response.status_code == 503 and "cannot read a photo" in response.text


def test_a_photo_form_without_its_token_is_refused(
    agent_client: TestClient, form_fields: Callable[..., Form], orders: Callable[..., tuple[Any, ...]]
) -> None:
    form_fields(agent_client)
    response = agent_client.post("/run-photo", data={"who": HOTEL},
                                 files={"image": ("list.png", DEMO_PHOTO.read_bytes(), "image/png")})

    assert response.status_code == 403 and "This form is out of date" in response.text
    assert orders(agent_client) == ()


def test_a_photo_form_must_come_from_a_demo_agent(agent_client: TestClient, send_photo: Callable[..., Any]) -> None:
    response = send_photo(agent_client, DEMO_PHOTO.read_bytes(), who="human:hotel-purchasing")

    assert response.status_code == 422 and "Choose who is asking" in response.text


def test_a_post_to_the_photo_page_that_is_not_a_form_with_a_file_is_refused(
    client: TestClient, form_fields: Callable[..., Form]
) -> None:
    response = client.post("/run-photo", data={**form_fields(client), "who": HOTEL})

    assert response.status_code == 422 and "multipart/form-data" in response.text


# --- the fourth example ------------------------------------------------------------------------------------


def test_the_fourth_example_sends_an_oat_drink_with_no_milk_statement_to_the_dietitian(
    client: TestClient, run_example: Callable[..., Any], only_order: Callable[..., Any]
) -> None:
    page = run_example(client, "scenario-4").text
    order = only_order(client)

    assert "Dietitian: oat drink with no milk statement" in client.get("/").text
    assert "Sent for approval" in page
    assert order.status is OrderStatus.PENDING_APPROVAL
    assert order.decision.required_roles == (ApproverRole.DIETITIAN,)
    assert "P-04" in order.decision.rule_ids
    assert order.option.lines[0].product_id == "469512"
