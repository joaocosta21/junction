"""Running a request from the first page: request -> lookup -> offer -> order or approval, in one click."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.contracts.common import OrderStatus

Post = Callable[..., Any]
MakeClient = Callable[..., TestClient]
SCENARIO_1 = "1,000 litres of lactose-free milk by Monday"


def _before_the_fold(page: str, marker: str = "<details") -> str:
    """The exclusions a reader sees without opening anything: from their heading to the collapsed rest."""
    start = page.index('id="excluded"')
    end = page.find(marker, start)
    return page[start:] if end == -1 else page[start:end]


def test_scenario_1_shows_a_confirmed_option_an_unconfirmed_alternative_and_the_exclusion_reasons(
    client: TestClient, run_example: Post
) -> None:
    response = run_example(client, "scenario-1")
    page = response.text

    assert response.status_code == 200
    assert "Best confirmed option" in page and "€2,580.64" in page
    assert "Alternative: quantity not confirmed" in page and "€1,010.00" in page
    assert "Quantity: confirmed" in page and "Quantity: not confirmed" in page
    assert "Cut-off passed" in page and "Order cut-off passed on" in page
    assert "Portion pack" in page and "463203" in page
    assert "Sent for approval" in page
    assert "Ordered by the agent" not in page


def test_scenario_1_names_the_rule_and_who_must_sign(client: TestClient, run_example: Post) -> None:
    page = run_example(client, "scenario-1").text

    assert "P-01" in page and "above the €750 limit per order" in page
    assert "F-01" in page  # the alternative: a quantity that is not confirmed always needs a human
    assert "purchasing manager" in page
    assert "A human must approve" in page


def test_scenario_1_shows_the_request_as_it_was_read_and_every_constraint_check(
    client: TestClient, run_example: Post
) -> None:
    page = run_example(client, "scenario-1").text

    assert "Monday 16 Nov 2026" in page
    assert "FREE_FROM_LACTOSE" in page and "1,000 L" in page
    assert "Every product offered is a bulk pack" in page  # a constraint check, with its sentence
    assert "Needed by: met" in page and "Quantity: not verified" in page


def test_exclusions_are_collapsed_after_the_first_five_and_every_reason_is_seen_first(
    client: TestClient, run_example: Post
) -> None:
    page = run_example(client, "scenario-1").text
    seen = _before_the_fold(page)

    assert seen.count('class="exclusion"') == 5
    assert "Show the other 14" in page
    assert page.count('class="exclusion"') == 19
    for reason in ("Cut-off passed", "Not deliverable", "Portion pack"):
        assert reason in seen
    assert "19 excluded" in page


def test_the_notes_of_an_offer_are_shown_under_the_exclusions(client: TestClient, run_example: Post) -> None:
    page = run_example(client, "scenario-1").text

    note = page.index("7 products fit the request and are in no option")
    assert note > page.index('id="excluded"')
    assert note < page.index('id="outcome"')


def test_the_result_reads_top_to_bottom_as_the_task_says(client: TestClient, run_example: Post) -> None:
    page = run_example(client, "scenario-1").text
    order = [page.index(f'id="{section}"') for section in ("request", "options", "excluded", "outcome")]

    assert order == sorted(order)
    first_option = page[page.index('id="options"'):page.index('id="excluded"')]
    lines, checks, verdict = (first_option.index(text) for text in ("Best confirmed option", "is a bulk pack", "P-01"))
    assert lines < checks < verdict


def test_scenario_2_is_sent_for_human_approval(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    page = run_example(client, "scenario-2").text
    order = only_order(client, "agent:allergy-ward")

    assert "Sent for approval" in page
    assert "A human must approve" in page
    assert "Declares an excluded allergen" in page
    assert "Allergens: confirmed" in page and "free from milk (AM)" in page
    assert (order.status, order.placed_by) == (OrderStatus.PENDING_APPROVAL, None)
    assert f"/orders/{order.order_id}" in page


def test_scenario_3_shows_which_listed_substitutes_fail_the_allergen_rule(
    client: TestClient, run_example: Post
) -> None:
    page = run_example(client, "scenario-3").text
    substitutes = page[page.index('id="substitutes"'):page.index('id="excluded"')]

    assert "With a substitute" in page and "475224" in page
    for product_id in ("471690", "471881", "464320"):
        assert product_id in substitutes
    assert substitutes.count("Fails the allergen rule") == 2
    assert "cereals containing gluten (AW, contains)" in substitutes
    assert "Listed by Valio Aimo" in substitutes
    assert "Cannot be ordered" in substitutes and "Can be ordered" in substitutes


def test_a_substitutes_price_is_set_apart_from_its_marks(client: TestClient, run_example: Post) -> None:
    page = run_example(client, "scenario-3").text
    substitutes = page[page.index('id="substitutes"'):page.index('id="excluded"')]

    assert '<span class="price">' in substitutes
    assert not re.search(r'</span><span class="price">', substitutes)  # "Cut-off passed€15.55" read as one word


def test_the_examples_work_without_a_model_and_the_page_says_how_the_request_was_read(
    client: TestClient, run_example: Post, parts: Any
) -> None:
    assert not parts.service.has_request_parser and not parts.service.has_agent_runner

    page = run_example(client, "scenario-2").text

    assert "typed request of this example" in page
    assert "No model was asked" in page


def test_a_pasted_text_that_equals_an_example_runs_as_that_example(client: TestClient, run_text: Post) -> None:
    page = run_text(client, f"  {SCENARIO_1}\n", who="agent:hotel-kitchen").text

    assert "Best confirmed option" in page and "Sent for approval" in page


def test_the_same_request_from_another_buyer_gets_that_buyers_rules(client: TestClient, run_text: Post) -> None:
    page = run_text(client, SCENARIO_1, who="agent:allergy-ward").text

    assert "Allergy ward agent (demo)" in page
    assert "Declares an excluded allergen" in page  # every milk declares milk
    assert "No option could be built" in page
    assert "Ordered by the agent" not in page and "Sent for approval" not in page


def test_free_text_without_a_parser_is_refused_with_a_way_forward(
    client: TestClient, run_text: Post, orders: Callable[..., Any]
) -> None:
    response = run_text(client, "ten crates of something nice")

    assert response.status_code == 503
    assert "no request parser running" in response.text
    assert "one of the examples" in response.text
    assert "ten crates of something nice" in response.text  # the text stays in the box
    assert orders(client) == ()


def test_free_text_is_read_by_the_parser_when_there_is_one(
    make_client: MakeClient, run_text: Post, fakes: Any
) -> None:
    parser = fakes.FakeParser()
    client = make_client(request_parser=parser)

    page = run_text(client, fakes.FREE_TEXT).text

    assert parser.texts == [fakes.FREE_TEXT]
    assert "read by the request parser" in page
    assert "plant_drink" in page and "80 L" in page
    assert "Sent for approval" in page


def test_what_the_parser_cannot_read_is_said_and_nothing_is_ordered(
    make_client: MakeClient, run_text: Post, fakes: Any, orders: Callable[..., Any]
) -> None:
    client = make_client(request_parser=fakes.FakeParser())

    response = run_text(client, "some milk for Monday <b>please</b>")

    assert response.status_code == 422
    assert "The request names no quantity." in response.text
    assert "<b>please</b>" not in response.text and "&lt;b&gt;please&lt;/b&gt;" in response.text
    assert orders(client) == ()


def test_the_buyer_agent_runs_the_request_when_there_is_one_and_its_steps_are_shown(
    make_client: MakeClient, run_text: Post, fakes: Any, only_order: Callable[..., Any]
) -> None:
    runner = fakes.FakeRunner()
    client = make_client(agent_runner=runner, request_parser=fakes.FakeParser())

    page = run_text(client, fakes.FREE_TEXT).text
    order = only_order(client)  # one order: the page did not run the request a second time itself

    assert runner.runs == 1
    steps = page[page.index('id="agent"'):]
    positions = [steps.index(tool) for tool in ("get_authority", "create_offer", "place_order")]
    assert positions == sorted(positions)
    assert "fake-model-1" in page and "recorded" in page
    assert "<b>from the model</b>" not in page
    assert "Sent for approval" in page and order.status is OrderStatus.PENDING_APPROVAL


def test_an_example_still_runs_when_the_model_behind_the_agent_cannot_be_reached(
    make_client: MakeClient, run_example: Post, fakes: Any, only_order: Callable[..., Any]
) -> None:
    client = make_client(agent_runner=fakes.DownRunner(), request_parser=fakes.NoParser())

    page = run_example(client, "scenario-2").text

    assert "The model behind the buyer agent cannot be reached right now." in page
    assert "typed request of this example" in page
    assert "Sent for approval" in page
    assert only_order(client, "agent:allergy-ward").status is OrderStatus.PENDING_APPROVAL


def test_free_text_the_agent_cannot_run_is_answered_with_its_reason_and_the_parser_is_not_asked_again(
    make_client: MakeClient, run_text: Post, fakes: Any, orders: Callable[..., Any]
) -> None:
    parser = fakes.FakeParser()
    client = make_client(agent_runner=fakes.DownRunner(), request_parser=parser)

    response = run_text(client, fakes.FREE_TEXT)

    assert response.status_code == 503
    assert "The model behind the buyer agent cannot be reached right now." in response.text
    assert parser.texts == []  # one reading per submission: the agent's (task FIX-10, finding 7)
    assert orders(client) == ()


def test_posting_the_same_form_twice_places_one_order(
    client: TestClient, form_fields: Callable[..., Any], only_order: Callable[..., Any]
) -> None:
    fields = form_fields(client)

    first = client.post("/run", data={**fields, "example": "scenario-2"})
    second = client.post("/run", data={**fields, "example": "scenario-2"})

    assert first.status_code == second.status_code == 200
    assert first.url == second.url
    assert only_order(client, "agent:allergy-ward").status is OrderStatus.PENDING_APPROVAL


def test_a_result_can_be_reloaded_and_does_not_order_again(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    first = run_example(client, "scenario-2")

    again = client.get(str(first.url))

    assert "?offer=off_" in str(first.url)
    assert again.status_code == 200 and "Sent for approval" in again.text
    only_order(client, "agent:allergy-ward")


def test_who_is_asking_is_remembered_in_a_cookie_not_in_the_address(client: TestClient, run_text: Post) -> None:
    response = run_text(client, SCENARIO_1, who="agent:allergy-ward")

    assert "allergy-ward" not in str(response.url)
    assert client.cookies.get("tta_agent") == "agent:allergy-ward"
    checked = re.search(r'<input[^>]*name="who"[^>]*value="([^"]+)"[^>]*checked', client.get("/").text)
    assert checked is not None and checked.group(1) == "agent:allergy-ward"


def test_only_a_demo_agent_can_be_chosen_as_the_one_asking(client: TestClient, run_text: Post) -> None:
    for who in ("human:hotel-purchasing", "supplier:valio-aimo", "agent:made-up"):
        response = run_text(client, SCENARIO_1, who=who)
        assert response.status_code == 422, who
        assert "Sent for approval" not in response.text


def test_an_empty_or_overlong_text_is_refused(client: TestClient, run_text: Post) -> None:
    assert run_text(client, "   ").status_code == 422
    assert run_text(client, "x" * 2001).status_code == 422


def test_an_offer_id_nobody_issued_is_a_404_page(client: TestClient) -> None:
    for offer_id in ("off_nobody", "a/b", "x" * 65):
        assert client.get("/", params={"offer": offer_id}).status_code == 404


def test_a_result_opens_at_a_summary_of_what_is_confirmed_what_is_not_and_what_was_excluded(
    client: TestClient, run_example: Post
) -> None:
    response = run_example(client, "scenario-1")
    page = response.text
    glance = page[page.index('id="glance"'):page.index('id="request"')]

    assert response.url.fragment == "glance"  # the browser opens the result at the summary, not at the form
    assert "3 confirmed products cover the 1,000 L asked for" in glance
    assert "Valio does not confirm the quantity in stock" in glance
    assert "19 products, each with its reason" in glance
    for reason in ("Cut-off passed", "Not deliverable", "Portion pack"):
        assert reason in glance
    assert "Sent for approval" in glance


def test_the_summary_sorts_options_by_what_the_data_confirms_not_by_their_kind(
    client: TestClient, run_example: Post
) -> None:
    page = run_example(client, "scenario-3").text
    confirmed = page[page.index('id="glance-confirmed"'):page.index('id="glance-unconfirmed"')]
    unconfirmed = page[page.index('id="glance-unconfirmed"'):page.index('id="glance-excluded"')]

    # The substitute rests on confirmed stock; the product asked for is the one Valio does not confirm.
    assert "475224" in confirmed and "Valio does not confirm" not in confirmed
    assert "Valio does not confirm the quantity in stock" in unconfirmed and "475224" not in unconfirmed
    assert "Sent for approval" in page[page.index('id="glance-outcome"'):page.index('id="request"')]


def test_an_agent_that_stops_without_an_offer_is_shown_with_its_report_and_its_steps(
    make_client: MakeClient, run_text: Post, fakes: Any, orders: Callable[..., Any]
) -> None:
    client = make_client(agent_runner=fakes.StoppedRunner(), request_parser=fakes.FakeParser())

    response = run_text(client, fakes.FREE_TEXT)
    page = response.text

    assert response.status_code == 200 and response.url.path == "/run"
    assert "No offer was built" in page
    assert "I could not tell which product is meant, so I asked for no offer." in page
    assert "get_authority" in page[page.index('id="agent"'):] and "stopped at the step limit" in page
    assert fakes.FREE_TEXT in page  # the text stays in the box
    assert orders(client) == ()
